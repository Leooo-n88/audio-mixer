# Audio Mixer para n8n + ElevenLabs

Microservicio FastAPI para mezclar voz generada por ElevenLabs con una música base.

## Archivos necesarios

- `main.py`
- `requirements.txt`
- `Dockerfile`
- `musica_base.mp3`

Agregá tu música y nombrala exactamente:

```text
musica_base.mp3
```

## Endpoints

### `POST /mix`

Recibe una sola voz y la mezcla con música.

Campos form-data:

```text
voice → archivo binario de ElevenLabs
order_id → ID de orden o ejecución
customer_name → nombre cliente
music_volume → 0.25
voice_offset_seconds → 120
fade_out_seconds → 6
```

### `POST /mix2`

Recibe dos partes de voz, las une y después las mezcla con música.
Ideal para ElevenLabs v3 cuando el guion supera el límite por request.

Campos form-data:

```text
voice_1 → primer MP3 de ElevenLabs
voice_2 → segundo MP3 de ElevenLabs
order_id → ID de orden o ejecución
customer_name → nombre cliente
music_volume → 0.25
voice_offset_seconds → 120
fade_out_seconds → 6
```

## Header de seguridad

```text
x-api-key → el mismo valor que pongas en API_SECRET en Railway
```

## Health check

```text
GET /
```

Debe devolver:

```json
{"status":"ok","service":"audio-mixer"}
```
