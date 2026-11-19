# Mando PC (connect-ai-qpp)

Controla tu laptop desde el celular: **pantalla en vivo, touchpad, teclado, volumen, bloquear/suspender/apagar y archivos** (bajar y subir).
Es una PWA (se instala en el iPhone como app) que habla con un programa pequeño que corre en tu laptop. No usa servidores de terceros ni cuentas: todo queda entre tu celular y tu laptop.

## Instalación (una sola vez, ~3 min)

1. Instala **Python 3** en la laptop (https://www.python.org/downloads/ — en Windows marca *Add Python to PATH*).
2. Abre el archivo de inicio:
   - **Windows:** doble clic en `iniciar.bat`
   - **Mac:** doble clic en `iniciar.command` (si macOS lo bloquea: clic derecho → Abrir)
   - **Linux:** `./iniciar.sh` (necesita sesión X11 y `xclip` para el portapapeles)
3. Se abre una página con un **código QR**. Escanéalo con la cámara del iPhone, ábrelo en Safari y toca **Compartir → Agregar a inicio**.

Listo: abres "Mando PC" y ves tu laptop. La laptop debe estar **encendida y despierta**.

## Usarla fuera de casa (recomendado: Tailscale, gratis)

1. Instala **Tailscale** en la laptop y en el iPhone, e inicia sesión con la misma cuenta.
2. En `/pair` (http://localhost:8765/pair en la laptop) aparece un segundo QR "Tailscale". Escanéalo y agrégalo a inicio.

Con eso funciona desde cualquier red sin abrir puertos en tu router. **No abras el puerto 8765 al internet.**

## Cómo se usa

| Pestaña | Qué hace |
|---|---|
| **Pantalla** | *Touchpad*: 1 dedo mueve, toque = clic, 2 dedos = scroll, toque con 2 dedos = clic derecho, toque + arrastre = arrastrar. *Tocar*: tocas donde quieres hacer clic. *Zoom*: pellizca para acercar. Botón **Teclado** para escribir en vivo. |
| **Teclado** | Escribir en vivo, texto largo, Ctrl/Alt/Shift/Win, flechas, F1–F12, atajos (copiar, pegar…), portapapeles de la laptop. |
| **Control** | Volumen, multimedia, tus atajos, abrir un enlace en la laptop, bloquear / suspender / reiniciar / apagar. Sensibilidad y calidad de imagen. |
| **Archivos** | Navega tus carpetas, descarga al celular, abre en la laptop, sube archivos. |

## Seguridad

- Cada celular entra con un **token secreto** (192 bits) que solo aparece en la página `/pair`, que **solo abre desde la propia laptop**.
- Solo acepta conexiones de redes privadas (Wi-Fi local y Tailscale). Bloquea IPs que fallan muchas veces.
- Los archivos solo se ven dentro de las carpetas permitidas (por defecto tu carpeta de usuario).
- ¿Perdiste el celular? Ejecuta `python mando.py --nuevo-token` (o `iniciar.bat --nuevo-token`): invalida todos los celulares.
- Quien tenga la app emparejada controla la laptop; bloquea tu iPhone con Face ID/código.

## Configuración

Se guarda en `~/.mando-pc/config.json` (en Windows `C:\Users\TU_USUARIO\.mando-pc\config.json`). Ahí puedes cambiar el puerto, las carpetas visibles, la carpeta de subidas y tus **atajos**:

```json
{"nombre": "Abrir mi correo", "icono": "📧", "url": "https://mail.google.com"}
{"nombre": "Mostrar escritorio", "icono": "🖥️", "teclas": ["win", "d"]}
{"nombre": "Abrir Excel", "icono": "📊", "ejecutar": "start excel"}
```

## Que arranque solo

- **Windows:** doble clic en `autoinicio-windows.bat` (después de haber abierto `iniciar.bat` al menos una vez).
- **Mac:** Ajustes del Sistema → General → Items de inicio → agrega `iniciar.command`.

## Limitaciones conocidas

- Windows: no se ve ni controla la pantalla de bloqueo ni las ventanas de administrador (UAC) a menos que ejecutes Mando PC como administrador.
- Mac: concede permisos de **Grabación de pantalla** y **Accesibilidad** a Terminal/Python cuando macOS los pida.
- Linux con Wayland no funciona; usa una sesión X11.
- Si la laptop se apaga o duerme, no hay forma de despertarla desde la app.
- Probado en Linux (X11). Los scripts de Windows/Mac siguen la misma lógica pero conviene confirmarlos en tu equipo.
