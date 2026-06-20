# Audio Mixer para n8n + ElevenLabs

Microservicio FastAPI para mezclar una voz generada por ElevenLabs con una música base.

## Archivos necesarios

- `main.py`
- `requirements.txt`
- `Dockerfile`
- `musica_base.mp3`

Importante: tenés que agregar tu música y nombrarla exactamente:

```text
musica_base.mp3
```

## Qué hace

- Música empieza en 0:00.
- Voz entra después de 120 segundos por defecto.
- Música queda al 25% por defecto.
- Música se corta cuando termina la voz.
- Agrega fade out final de 6 segundos por defecto.
- Devuelve un MP3 final.

## Endpoint

```text
POST /mix
```

## Campos form-data desde n8n

```text
voice → archivo binario de ElevenLabs
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
