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
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]

    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return float(result.stdout.decode("utf-8").strip())


def save_upload(upload: UploadFile, path: str) -> None:
    with open(path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)


def concat_audio_files(input_paths: list[str], output_path: str) -> None:
    """Une varias partes de voz en un solo MP3, re-encodeando para evitar cortes raros."""
    list_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_concat.txt")
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for path in input_paths:
                safe_path = path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        command = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            output_path,
        ]

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    finally:
        try:
            if os.path.exists(list_path):
                os.remove(list_path)
        except Exception:
            pass


def mix_voice_with_music(
    voice_path: str,
    output_path: str,
    music_volume: float,
    voice_offset_seconds: int,
    fade_out_seconds: int,
) -> None:
    voice_duration = get_audio_duration_seconds(voice_path)
    total_duration = float(voice_offset_seconds) + voice_duration

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
        output_path,
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def auth_ok(x_api_key: str | None) -> bool:
    return not API_SECRET or x_api_key == API_SECRET


def make_safe_name(customer_name: str) -> str:
    return "".join(c for c in customer_name if c.isalnum()) or "cliente"


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
    """Endpoint original: recibe una sola voz y la mezcla con musica_base.mp3."""

    if not auth_ok(x_api_key):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    if not os.path.exists(MUSIC_FILE):
        return JSONResponse(
            status_code=500,
            content={"error": "No existe musica_base.mp3 en el servicio"},
        )

    safe_name = make_safe_name(customer_name)
    job_id = str(uuid.uuid4())

    voice_path = os.path.join(TEMP_DIR, f"{job_id}_voice.mp3")
    output_path = os.path.join(TEMP_DIR, f"{order_id}-{safe_name}-final.mp3")

    try:
        save_upload(voice, voice_path)
        mix_voice_with_music(
            voice_path=voice_path,
            output_path=output_path,
            music_volume=music_volume,
            voice_offset_seconds=voice_offset_seconds,
            fade_out_seconds=fade_out_seconds,
        )

    except subprocess.CalledProcessError as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error procesando audio con FFmpeg/FFprobe",
                "details": e.stderr.decode("utf-8", errors="ignore"),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Error inesperado mezclando audio", "details": str(e)},
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
        filename=f"{order_id}-{safe_name}-final.mp3",
    )


@app.post("/mix2")
async def mix_two_audio_parts(
    voice_1: UploadFile = File(...),
    voice_2: UploadFile = File(...),
    order_id: str = Form("test"),
    customer_name: str = Form("cliente"),
    music_volume: float = Form(0.25),
    voice_offset_seconds: int = Form(120),
    fade_out_seconds: int = Form(6),
    x_api_key: str | None = Header(default=None),
):
    """
    Recibe dos partes de voz generadas por ElevenLabs v3.
    Primero une voice_1 + voice_2 en una sola voz larga.
    Después mezcla esa voz larga con musica_base.mp3.
    """

    if not auth_ok(x_api_key):
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    if not os.path.exists(MUSIC_FILE):
        return JSONResponse(
            status_code=500,
            content={"error": "No existe musica_base.mp3 en el servicio"},
        )

    safe_name = make_safe_name(customer_name)
    job_id = str(uuid.uuid4())

    voice_1_path = os.path.join(TEMP_DIR, f"{job_id}_voice_1.mp3")
    voice_2_path = os.path.join(TEMP_DIR, f"{job_id}_voice_2.mp3")
    joined_voice_path = os.path.join(TEMP_DIR, f"{job_id}_voice_joined.mp3")
    output_path = os.path.join(TEMP_DIR, f"{order_id}-{safe_name}-final.mp3")

    cleanup_paths = [voice_1_path, voice_2_path, joined_voice_path]

    try:
        save_upload(voice_1, voice_1_path)
        save_upload(voice_2, voice_2_path)

        concat_audio_files([voice_1_path, voice_2_path], joined_voice_path)

        mix_voice_with_music(
            voice_path=joined_voice_path,
            output_path=output_path,
            music_volume=music_volume,
            voice_offset_seconds=voice_offset_seconds,
            fade_out_seconds=fade_out_seconds,
        )

    except subprocess.CalledProcessError as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error procesando audio con FFmpeg/FFprobe",
                "details": e.stderr.decode("utf-8", errors="ignore"),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Error inesperado mezclando audio", "details": str(e)},
        )
    finally:
        for path in cleanup_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    return FileResponse(
        output_path,
        media_type="audio/mpeg",
        filename=f"{order_id}-{safe_name}-final.mp3",
    )
