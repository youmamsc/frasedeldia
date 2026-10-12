# Frase del Día 🎙️

**Cuatro podcasts de humor para aprender expresiones sin sonar como un robot.**

Este repositorio contiene los cuatro **episodios piloto**: tres para aprender español coloquial desde inglés, francés e italiano y uno para hispanohablantes que quieren hablar inglés de forma natural, sin traducciones literales.

| Idioma del programa | Expresión | Episodio |
|---|---|---|
| 🇬🇧 Inglés | ¡Ni de coña! | `samples/frasedeldia-en-ni-de-cona.mp3` |
| 🇫🇷 Francés | ¡Ni de coña! | `samples/frasedeldia-fr-ni-de-cona.mp3` |
| 🇮🇹 Italiano | ¡Ni de coña! | `samples/frasedeldia-it-ni-de-cona.mp3` |
| 🇪🇸 Español | “From lost to the river” | `samples/frasedeldia-es-from-lost-to-the-river.mp3` |

## Cómo escuchar los pilotos

Los cuatro MP3 estarán en [`samples/`](https://github.com/youmamsc/frasedeldia/tree/main/samples) después de que termine correctamente la primera ejecución de **GitHub Actions → Generate four podcast pilots**. También se podrá descargar el archivo ZIP `frase-del-dia-four-pilots` desde la ejecución de Actions.

## Cómo volver a producirlos

1. En GitHub, entra en **Actions → Generate four podcast pilots**.
2. Pulsa **Run workflow**.
3. Descarga el artifact o accede a los audios versionados en `samples/`.

La acción también se lanza al cambiar los guiones o el motor de voz, siempre que sea en `main`.

## Tecnología, costes y privacidad

* Python, `edge-tts` (voces neurales gratuitas sin API key) y FFmpeg/`pydub`.
* Cada idioma usa un narrador propio; las expresiones españolas se pronuncian con voz de España.
* Si Edge TTS no está disponible, se usa un motor local de emergencia (`espeak`) y se marca en `samples/manifest.json`. La calidad del fallback es inferior.
* GitHub Actions estándar en un repositorio público: no consume la cuota de minutos de repositorios privados; las políticas y límites de uso de GitHub pueden cambiar.
* **No se usa Gemini, ninguna clave de MAC FM, Telegram ni Spotify.** Esta primera fase es solo una prueba de audio.
* Los guiones son humorísticos y contienen lenguaje adulto/vulgar.

## Organización

`episodes/pilots.json`: guiones y segmentos de los cuatro episodios.

`src/build_pilots.py`: sintetiza, une y normaliza los segmentos en MP3.

`.github/workflows/pilots.yml`: ejecuta pruebas, genera MP3 y publica los ejemplos.

`tests/test_pilots.py`: valida estructura y contenidos básicos del paquete.
