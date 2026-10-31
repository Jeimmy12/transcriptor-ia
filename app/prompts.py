"""Prompts. Van en el mensaje del usuario (Gemma no siempre admite system instructions)."""

TRANSCRIBE = """Eres un transcriptor profesional de español. Transcribe fielmente el audio adjunto.

Reglas:
- Escribe en español con ortografía, tildes, mayúsculas y puntuación correctas.
- Conserva lo que se dice, sin resumir ni interpretar. Puedes omitir ruidos y balbuceos ininteligibles.
- Separa en párrafos cuando cambie el tema o el interlocutor.
- Este audio es el bloque {i} de {n} de una grabación más larga: puede empezar o terminar a mitad de frase. No completes frases ni inventes contenido.
- Si una palabra es dudosa, escribe tu mejor interpretación; no agregues notas.
- Si no hay voz humana, responde exactamente: [SILENCIO]
{context}
Devuelve únicamente la transcripción, sin encabezados ni comentarios."""

CONTEXT = """
Contexto del final del bloque anterior (solo para nombres y términos; NO lo repitas):
\"\"\"{tail}\"\"\"
"""

POLISH = """Eres un editor de textos en español. Te paso un fragmento de una transcripción automática.
Mejora su redacción sin cambiar su contenido:
- Corrige ortografía, tildes, puntuación y mayúsculas.
- Elimina muletillas, titubeos y repeticiones involuntarias (eh, mmm, o sea, ¿no?, etc.).
- Organiza en párrafos claros.
- NO resumas, NO agregues información, NO cambies cifras, nombres ni términos técnicos.
- El fragmento puede empezar o terminar a mitad de frase: déjalo así, no lo completes.
Devuelve únicamente el texto corregido.

Fragmento:
\"\"\"
{text}
\"\"\""""

PARTIAL = """Estás leyendo la parte {i} de {n} de la transcripción de una grabación larga.
Extrae notas detalladas y fieles en español, en viñetas: temas, datos y cifras, nombres, decisiones, acuerdos, tareas (con responsable y fecha si se mencionan) y dudas abiertas.
No inventes nada y no redactes conclusiones generales.

Texto:
\"\"\"
{text}
\"\"\""""

MINUTA = """Eres un asistente experto en redactar minutas profesionales en español.
A partir de la {kind} que aparece abajo, redacta una minuta clara y fiel al contenido.
No inventes datos: si algo no se menciona, escribe "No especificado".

Usa exactamente esta estructura en Markdown:

# Minuta: <título breve deducido del contenido>

## Resumen ejecutivo
(3 a 6 líneas)

## Participantes y contexto
- ...

## Temas tratados
### <tema>
- ...

## Puntos clave
- ...

## Decisiones y acuerdos
- ...

## Tareas y próximos pasos
- [ ] Tarea — Responsable: ... — Fecha: ...

## Pendientes o preguntas abiertas
- ...

Reglas: solo encabezados, viñetas y **negritas** (sin tablas); español neutro y profesional; ningún comentario fuera de la minuta.

Material ({kind}):
\"\"\"
{material}
\"\"\""""
