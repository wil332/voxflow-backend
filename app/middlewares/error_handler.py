from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

def setup_exception_handlers(app: FastAPI):
    
    # 1. Menangkap Error HTTP bawaan FastAPI/Starlette (contoh: 404 Not Found, 405 Method Not Allowed)
    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "code": exc.status_code,
                "message": exc.detail,
                "path": request.url.path
            }
        )

    # 2. Menangkap Error Validasi Data (contoh: Parameter body/query salah tipe data)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": 422,
                "message": "Kesalahan validasi data masukan (parameter tidak sesuai).",
                "details": exc.errors(),
                "path": request.url.path
            }
        )

    # 3. Menangkap Error Umum yang Tidak Terduga (Internal Server Error 500)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": 500,
                "message": "Terjadi kesalahan internal pada server backend.",
                "error_detail": str(exc),
                "path": request.url.path
            }
        )