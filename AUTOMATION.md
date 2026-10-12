# La Frase del Día 🎙️

Cuatro micro-podcasts diarios, una sola expresión española aprobada por Telegram.

- **English / Français / Italiano:** español real, pronunciación auténtica, traducción, situaciones absurdas y humor adulto.
- **Español → English:** empieza por la traducción literal absurda en inglés, explica la expresión española y enseña una alternativa idiomática correcta en inglés.
- **Duración:** objetivo 45–60 segundos por idioma.
- **Política editorial:** ninguna expresión se publica sin aprobación; botón **Aprobar** o **Cambiar** en Telegram.
- **Distribución:** 4 feeds RSS independientes preparados para registrar en Spotify for Creators.
- **Separado de MAC FM:** no reutiliza sus secretos, repositorios ni tareas programadas.

## Flujo

1. **Domingo, 18:13 (Europe/Paris):** Gemini elige 7 expresiones nuevas a partir de un catálogo de español coloquial y manda 7 mensajes de Telegram, uno por día de la semana siguiente.
2. **Telegram:** apruebas o pides otra expresión. GitHub comprueba tus respuestas cada 15 minutos; no hace falta servidor de bot ni webhook.
3. **Diariamente a las 09:17:** si la frase para ese día está aprobada, Gemini crea cuatro guiones distintos, Edge TTS produce el audio y el sistema actualiza los 4 RSS.
4. **10:17:** segundo intento idempotente ante un fallo anterior. Si ya se publicó, no se repite.

Los horarios GitHub Actions son orientativos: GitHub puede retrasar tareas cron. Para puntualidad, se puede añadir posteriormente cron-job.org sin cambiar el flujo.

## Configuración inicial (una sola vez)

En [Settings → Secrets and variables → Actions](https://github.com/youmamsc/frasedeldia/settings/secrets/actions), añadir **Repository secrets**:

| Secret | Valor |
| --- | --- |
| GEMINI_API_KEY | Clave de IA Studio para *este* proyecto. No copies la de MAC FM si quieres separar cuotas. |
| TELEGRAM_BOT_TOKEN | Token de un bot NUEVO creado con @BotFather (no publicar ni compartir en chat). |
| TELEGRAM_CHAT_ID | ID numérico de tu chat privado con ese bot. Envía /start al bot primero; coincide con tu ID de usuario. |
| PODCAST_OWNER_EMAIL | Dirección de correo que aparecerá **públicamente** en los RSS y recibirá la verificación de Spotify. Mejor un alias específico. |

Si configuras también **Repository variable** GEMINI_TEXT_MODEL, se usará en lugar del valor por defecto gemini-2.5-flash.

**Importante:** en **Variables**, define ENABLE_PUBLICATION = true **solo cuando quieras empezar la publicación**. Sin esa variable, la producción diaria no genera ni publica nada. La selección semanal y las respuestas de Telegram sí pueden probarse una vez configurados los secretos.

Para averiguar TELEGRAM_CHAT_ID, tras enviar /start al bot, visita personalmente desde tu navegador (no pegues el token en un chat) https://api.telegram.org/bot<TU_TOKEN>/getUpdates ; busca message.chat.id. Usa un bot dedicado, sin webhook.

## Ensayos

- Actions → **La frase del día** → Run workflow → **tests** para comprobar las reglas sin usar servicios externos.
- Run workflow → **weekly** para enviar las siete propuestas inmediatamente (requiere Gemini + Telegram).
- Run workflow → **poll** para procesar respuestas sin esperar al cron.
- Run workflow → **daily** para publicar la expresión aprobada de hoy (requiere ENABLE_PUBLICATION=true).

## RSS

Después de la primera publicación, los cuatro feeds serán:

- English: https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public/en/feed.xml
- Français: https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public/fr/feed.xml
- Italiano: https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public/it/feed.xml
- Español (aprende inglés): https://raw.githubusercontent.com/youmamsc/frasedeldia/main/public/es/feed.xml

Registra **cada feed** como programa independiente en https://creators.spotify.com/ → Add a new show → Somewhere else. Confirma la propiedad desde el correo incluido en su RSS. Spotify importa episodios según su frecuencia de lectura; no es instantáneo.

## Costes, fiabilidad y privacidad

- GitHub Actions en repositorios públicos con runners estándar: ejecución gratuita conforme a las políticas de GitHub. Cron con frecuencia mínima de 5 min; aquí usamos 15 min para Telegram.
- Gemini: **depende de las cuotas vigentes del proyecto y modelo**; no se puede prometer ilimitado ni coste cero sin verificar tu cuenta. No se configura facturación de pago desde este proyecto.
- Edge TTS: alternativa sin coste explícito por uso pero **no es una API pública con SLA ni garantía de disponibilidad**. Si falla o limita las llamadas, el episodio no se publica.
- El historial de expresiones, guiones y audios es **público** en este repositorio. Nunca se almacenan tokens aquí.
- Los cuatro podcasts se marcan como **explicit** debido al humor y lenguaje adulto. No confundir con contenido infantil.
- El programa se detiene ante cuotas, credenciales ausentes, problemas de audio o una frase sin aprobar: **no publica contenido inventado ni se salta tu visto bueno**.

## Desarrollo

Python 3.12:

    pip install -r requirements.txt
    python -m unittest discover -s automation/tests -v

Las ejecuciones con credenciales y la distribución **todavía requieren configuración**. Un commit de código no equivale a un podcast activo ni a un programa ya registrado en Spotify.
