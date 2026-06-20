from fastapi import FastAPI, UploadFile, File, Form, Header
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import uuid
import os
import shutil

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_FILE = os.path.join(BASE_DIR, "musica_base.mp3")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

# En Railway vas a crear esta variable.
# En n8n vas a mandar el mismo valor en el header x-api-key.
API_SECRET = os.getenv("API_SECRET", "")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "audio-mixer"}


def get_audio_duration_seconds(file_path: str) -> float:
    """
    Usa ffprobe para calcular la duración de la voz.
    Esto nos permite cortar el audio final exactamente cuando termina la voz,
    sumando el offset inicial de música.
    """
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return float(result.stdout.decode("utf-8").strip())


@app.post("/mix")
async def mix_audio(
    voice: UploadFile = File(...),
    order_id: str = Form("test"),
    customer_name: str = Form("cliente"),
    music_volume: float = Form(0.25),
    voice_offset_seconds: int = Form(120),
    fade_out_seconds: int = Form(6),
    x_api_key: str | None = Header(default=None),
):
    """
    Recibe una voz generada por ElevenLabs y la mezcla con musica_base.mp3.

    Resultado:
    - La música empieza en 0:00.
    - La voz entra después de voice_offset_seconds.
    - La música baja al volumen indicado.
    - La música se corta cuando termina la voz.
    - El final tiene fade out suave.
    - Devuelve final.mp3.
    """

    if API_SECRET and x_api_key != API_SECRET:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized"}
        )

    if not os.path.exists(MUSIC_FILE):
        return JSONResponse(
            status_code=500,
            content={"error": "No existe musica_base.mp3 en el servicio"}
        )

    safe_name = "".join(c for c in customer_name if c.isalnum()) or "cliente"
    job_id = str(uuid.uuid4())

    voice_path = os.path.join(TEMP_DIR, f"{job_id}_voice.mp3")
    output_path = os.path.join(TEMP_DIR, f"{order_id}-{safe_name}-final.mp3")

    try:
        with open(voice_path, "wb") as buffer:
            shutil.copyfileobj(voice.file, buffer)

        voice_duration = get_audio_duration_seconds(voice_path)
        total_duration = float(voice_offset_seconds) + voice_duration

        # Fade out: si el audio es muy corto, lo ajusta para que no falle.
        fade_duration = max(0.0, min(float(fade_out_seconds), total_duration / 3))
        fade_start = max(0.0, total_duration - fade_duration)

        delay_ms = int(voice_offset_seconds) * 1000

        if fade_duration > 0:
            filter_complex = (
                f"[0:a]volume={music_volume}[music];"
                f"[1:a]adelay={delay_ms}:all=true[voice];"
                f"[music][voice]amix=inputs=2:duration=shortest:dropout_transition=0[mix];"
                f"[mix]afade=t=out:st={fade_start}:d={fade_duration}[aout]"
            )
        else:
            filter_complex = (
                f"[0:a]volume={music_volume}[music];"
                f"[1:a]adelay={delay_ms}:all=true[voice];"
                f"[music][voice]amix=inputs=2:duration=shortest:dropout_transition=0[aout]"
            )

        command = [
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",
            "-i", MUSIC_FILE,
            "-i", voice_path,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-t", str(total_duration),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            output_path
        ]

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    except subprocess.CalledProcessError as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error procesando audio con FFmpeg/FFprobe",
                "details": e.stderr.decode("utf-8", errors="ignore")
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error inesperado mezclando audio",
                "details": str(e)
            }
        )
    finally:
        try:
            if os.path.exists(voice_path):
                os.remove(voice_path)
        except Exception:
            pass

    return FileResponse(
        output_path,
        media_type="audio/mpeg",
        filename=f"{order_id}-{safe_name}-final.mp3"
    )
