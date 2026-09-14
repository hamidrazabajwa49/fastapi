"""
Stage 1 - Basic Patient Management API

The starting point of this project. A minimal FastAPI service that reads
patient records from a JSON file and exposes them through a handful of
read-only endpoints.

What this stage does NOT have (on purpose, so the next stages can show
the improvement):
    - No Pydantic models -> no request/response validation at all.
    - No way to create, update, or delete a patient (read-only API).
    - No error handling around the JSON file itself.

Run it with:
    uvicorn main:app --reload
"""

import json

from fastapi import FastAPI, HTTPException, Path, Query

app = FastAPI(title="Patient Management API - Stage 1 (Basic)")

DATA_FILE = "patients.json"


def load_patients() -> dict:
    """Read all patient records from the JSON data file.

    Returns:
        dict: A mapping of patient_id -> patient record.
    """
    with open(DATA_FILE, "r") as f:
        return json.load(f)


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
def view_patient(
    patient_id: str = Path(
        ...,
        description="The ID of the patient to look up",
        examples=["P001"],
    )
):
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
