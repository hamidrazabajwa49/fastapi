"""
Stage 3 - Full CRUD API

The final stage. Builds on Stage 2 by adding the two operations a real
patient-management system needs: updating a patient's details, and removing
a patient from the records.

Two bugs from the original code-along were fixed here:
    1. `delete_record` deleted the patient from the in-memory dict but never
        called `save_patients()`, so deletions never actually persisted to
        disk. Fixed by saving after the delete.
    2. `update_record` called `model_dump(exclude='ID')`. A bare string is
        iterable character-by-character, so Pydantic silently treated this as
        "exclude fields named 'I' and 'D'" instead of excluding the `id`
        field. Fixed by passing a proper set: `exclude={"id"}`.

Run it with:
    uvicorn application:app --reload
"""

import json
from typing import Annotated, Literal, Optional

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, computed_field

DATA_FILE = "patients.json"


class Patient(BaseModel):
    """Represents a single, complete patient record."""

    id: Annotated[str, Field(..., title="Patient ID", examples=["P001"])]
    name: Annotated[str, Field(..., title="Patient's full name")]
    age: Annotated[int, Field(..., gt=0, lt=100, title="Patient's age in years")]
    gender: Annotated[Literal["male", "female", "other"], Field(..., title="Patient's gender")]
    city: Annotated[str, Field(..., title="City the patient lives in")]
    height: Annotated[float, Field(..., gt=0, title="Height in centimeters")]
    weight: Annotated[float, Field(..., gt=0, title="Weight in kilograms")]

    @computed_field
    @property
    def bmi(self) -> float:
        """Body Mass Index, calculated from height (cm) and weight (kg)."""
        height_m = self.height / 100
        return round(self.weight / (height_m**2), 2)

    @computed_field
    @property
    def verdict(self) -> str:
        """A simple BMI category derived from `bmi`."""
        bmi = self.bmi
        if bmi < 18.5:
            return "Underweight"
        elif bmi < 30:
            return "Normal"
        else:
            return "Obese"


class PatientUpdate(BaseModel):
    """Same fields as `Patient`, but every field is optional.

    Used for PUT/PATCH-style partial updates: only the fields the client
    actually sends are changed, everything else is left as-is.
    """

    name: Annotated[Optional[str], Field(None, title="Patient's full name")]
    age: Annotated[Optional[int], Field(None, gt=0, lt=100, title="Patient's age in years")]
    gender: Annotated[Optional[Literal["male", "female", "other"]],Field(None, title="Patient's gender")]
    city: Annotated[Optional[str], Field(None, title="City the patient lives in")]
    height: Annotated[Optional[float], Field(None, gt=0, title="Height in centimeters")]
    weight: Annotated[Optional[float], Field(None, gt=0, title="Weight in kilograms")]


app = FastAPI(title="Patient Management API - Stage 3 (Full CRUD)")


def load_patients() -> dict:
    """Read all patient records from the JSON data file.

    Returns an empty dict if the file doesn't exist yet, so the API still
    works on a completely fresh checkout.
    """
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_patients(patients: dict) -> None:
    """Persist the full patients dict back to the JSON data file."""
    with open(DATA_FILE, "w") as f:
        json.dump(patients, f, indent=2)


@app.get("/")
def root():
    """Simple health/welcome endpoint."""
    return {"message": "Patient Management System API"}


@app.get("/about")
def about():
    """Short description of what this API does."""
    return {"message": "A fully functional API to manage your patient records"}


@app.get("/view")
def view_all_patients():
    """Return every patient record currently stored."""
    return load_patients()


@app.get("/patient/{patient_id}")
def view_patient(patient_id: str = Path(..., description="The ID of the patient to look up", examples=["P001"])):
    """Return a single patient record by its ID.

    Raises:
        HTTPException(404): if the patient ID is not found.
    """
    patients = load_patients()

    if patient_id in patients:
        return patients[patient_id]

    raise HTTPException(status_code=404, detail="This patient doesn't exist in the records")


@app.get("/sort")
def sort_patients(
    sort_by: str = Query(..., description="Sort by: age, height, or weight"),
    order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    ):
    """Return every patient sorted by a numeric field.

    Raises:
        HTTPException(400): if `sort_by` or `order` is not a supported value.
    """
    sortable_fields = ["age", "height", "weight"]

    if sort_by not in sortable_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Choose a valid field to sort by: {sortable_fields}",
        )
    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Order must be 'asc' or 'desc'")

    patients = load_patients()
    reverse_order = order == "desc"

    return sorted(patients.values(), key=lambda p: p.get(sort_by, 0), reverse=reverse_order)


@app.post("/create", status_code=201)
def add_patient(patient: Patient):
    """Create a new patient record.

    Example request body:
        {
            "id": "P022",
            "name": "Ayesha Khan",
            "age": 27,
            "gender": "female",
            "city": "Lahore",
            "height": 163.0,
            "weight": 57.0
        }

    Raises:
        HTTPException(400): if a patient with the same ID already exists.
    """
    patients = load_patients()

    if patient.id in patients:
        raise HTTPException(status_code=400, detail="A patient with this ID already exists")

    patients[patient.id] = patient.model_dump(exclude={"id"})
    save_patients(patients)

    return JSONResponse(status_code=201, content={"message": "Patient's data added!"})


@app.put("/edit/{patient_id}")
def update_patient(patient_id: str, patient_update: PatientUpdate):
    """Update one or more fields of an existing patient.

    Only fields present in the request body are changed; everything else
    keeps its current value. `bmi` and `verdict` are recalculated
    automatically if height or weight changes.

    Example request body (only updating weight):
        { "weight": 68.5 }

    Raises:
        HTTPException(404): if the patient ID is not found.
    """
    patients = load_patients()

    if patient_id not in patients:
        raise HTTPException(status_code=404, detail="This patient doesn't exist in the records")

    existing_record = patients[patient_id]
    fields_to_update = patient_update.model_dump(exclude_unset=True)

    for field, value in fields_to_update.items():
        existing_record[field] = value

    # Re-validate the full, merged record through the Patient model so that
    # constraints (age range, gender enum, etc.) and the computed fields
    # (bmi, verdict) stay correct after the update.
    existing_record["id"] = patient_id
    validated_patient = Patient(**existing_record)

    patients[patient_id] = validated_patient.model_dump(exclude={"id"})
    save_patients(patients)

    return JSONResponse(status_code=200, content={"message": "Patient's record updated"})


@app.delete("/delete/{patient_id}")
def delete_patient(patient_id: str):
    """Permanently delete a patient record.

    Raises:
        HTTPException(404): if the patient ID is not found.
    """
    patients = load_patients()

    if patient_id not in patients:
        raise HTTPException(status_code=404, detail="No patient with this ID")

    del patients[patient_id]
    save_patients(patients)

    return JSONResponse(status_code=200, content={"message": "Patient's record deleted"})
