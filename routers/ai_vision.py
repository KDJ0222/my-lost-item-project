from fastapi import APIRouter, File, Request, UploadFile

from schemas import ImageAnalysisResponse, ImageUploadResponse
from services.gemini import analyze_image
from services.images import read_image, save_image


router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("", response_model=ImageUploadResponse, status_code=201)
def upload_image(request: Request, file: UploadFile = File(...)):
    data, extension, _ = read_image(file)
    image_path, _ = save_image(data, extension, request.app.state.upload_dir)
    return ImageUploadResponse(image_path=image_path)


@router.post("/analyze", response_model=ImageAnalysisResponse, status_code=201)
def upload_and_analyze(request: Request, file: UploadFile = File(...)):
    data, extension, mime_type = read_image(file)
    analysis = analyze_image(data, mime_type)
    # Save after a successful analysis so failures leave no orphan file.
    image_path, _ = save_image(data, extension, request.app.state.upload_dir)
    return ImageAnalysisResponse(image_path=image_path, **analysis.model_dump())
