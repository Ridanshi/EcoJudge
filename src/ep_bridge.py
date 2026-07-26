"""EnergyPlus integration: load/patch the IDF via eppy, run the simulation as a
subprocess, parse errors, and extract per-time-block metrics from the CSV output."""
import csv
import os
import subprocess

from eppy.modeleditor import IDF

from src.comfort import compute_pmv

ENERGYPLUS_EXE = os.environ.get("ENERGYPLUS_EXE", "C:/EnergyPlusV23-2-0/energyplus.exe")
ENERGYPLUS_IDD = os.environ.get("ENERGYPLUS_IDD", "C:/EnergyPlusV23-2-0/Energy+.idd")

BLOCKS = [
    {"name": "night", "until": "6:00", "hours": range(1, 7)},
    {"name": "morning", "until": "12:00", "hours": range(7, 13)},
    {"name": "afternoon", "until": "18:00", "hours": range(13, 19)},
    {"name": "evening", "until": "24:00", "hours": range(19, 25)},
]

_IDD_SET = False


def load_idf(idf_path: str, weather_path: str) -> IDF:
    global _IDD_SET
    if not _IDD_SET:
        IDF.setiddname(ENERGYPLUS_IDD)
        _IDD_SET = True
    return IDF(idf_path, weather_path)


def apply_patch(idf: IDF, verdicts: dict) -> None:
    for schedule_name, key in (("Htg-SetP-Sch", "heating_setpoint_c"), ("Clg-SetP-Sch", "cooling_setpoint_c")):
        existing = [s for s in idf.idfobjects["SCHEDULE:COMPACT"] if s.Name == schedule_name]
        for obj in existing:
            idf.removeidfobject(obj)

        new_obj = idf.newidfobject("SCHEDULE:COMPACT", Name=schedule_name)
        new_obj.Schedule_Type_Limits_Name = "Temperature"
        new_obj.Field_1 = "Through: 12/31"
        new_obj.Field_2 = "For: AllDays"
        field_index = 3
        for block in BLOCKS:
            setattr(new_obj, f"Field_{field_index}", f"Until: {block['until']}")
            setattr(new_obj, f"Field_{field_index + 1}", verdicts[block["name"]][key])
            field_index += 2


def save_idf(idf: IDF, path: str) -> None:
    idf.saveas(path)


def run_sim(idf_path: str, weather_path: str, out_dir: str) -> None:
    if not os.path.exists(ENERGYPLUS_EXE):
        raise RuntimeError(f"EnergyPlus executable not found at {ENERGYPLUS_EXE}")
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        [ENERGYPLUS_EXE, "-w", weather_path, "-r", "-d", out_dir, idf_path],
        capture_output=True,
        text=True,
        timeout=120,
    )


def get_errors(out_dir: str) -> list:
    err_path = os.path.join(out_dir, "eplusout.err")
    if not os.path.exists(err_path):
        return [f"eplusout.err not found in {out_dir} -- simulation likely did not run"]
    severe_lines = []
    with open(err_path) as f:
        for line in f:
            if "** Severe" in line or "** Fatal" in line:
                severe_lines.append(line.strip())
    return severe_lines


def _hour_of_row(date_time_value: str) -> int:
    return int(date_time_value.strip().split()[-1].split(":")[0])


def _block_for_hour(hour: int) -> str:
    for block in BLOCKS:
        if hour in block["hours"]:
            return block["name"]
    raise ValueError(f"hour {hour} not in any block")


def get_block_metrics(out_dir: str, zone_name: str = "SPACE1-1") -> dict:
    csv_path = os.path.join(out_dir, "eplusout.csv")
    temp_col = f"{zone_name}:Zone Air Temperature [C](Hourly)"
    rh_col = f"{zone_name}:Zone Air Relative Humidity [%](Hourly)"
    kwh_col = "Electricity:Facility [J](Hourly)"

    sums = {b["name"]: {"temp": 0.0, "rh": 0.0, "kwh_j": 0.0, "count": 0} for b in BLOCKS}

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        for row in reader:
            hour = _hour_of_row(row["Date/Time"])
            block_name = _block_for_hour(hour)
            sums[block_name]["temp"] += float(row[temp_col])
            sums[block_name]["rh"] += float(row[rh_col])
            sums[block_name]["kwh_j"] += float(row[kwh_col])
            sums[block_name]["count"] += 1

    result = {}
    for block_name, acc in sums.items():
        count = acc["count"] or 1
        avg_temp = acc["temp"] / count
        avg_rh = acc["rh"] / count
        result[block_name] = {
            "avg_temp_c": avg_temp,
            "avg_rh_pct": avg_rh,
            "avg_pmv": compute_pmv(avg_temp, avg_rh),
            "kwh": acc["kwh_j"] / 3.6e6,
        }
    return result
