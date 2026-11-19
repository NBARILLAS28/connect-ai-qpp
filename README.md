# Mando PC (connect-ai-qpp)

Controla tu laptop desde el celular: **pantalla en vivo, touchpad, teclado, volumen, bloquear/suspender/apagar y archivos** (bajar y subir).
Es una PWA (se instala en el iPhone como app) que habla con un programa pequeño que corre en tu laptop. No usa servidores de terceros ni cuentas: todo queda entre tu celular y tu laptop.

Funciona igual en **Windows y Mac** (y Linux con X11). Si usas las dos, instálala en cada una: cada laptop queda como una app distinta en tu iPhone, con su nombre ("Mando · MiLaptop").

## Instalación (una sola vez por laptop, ~3 min)

Descarga o clona este repo en la laptop y sigue los pasos de tu sistema.

### Windows
1. Instala **Python 3** (https://www.python.org/downloads/) marcando *Add Python to PATH*.
2. Doble clic en **`iniciar.bat`**. La primera vez instala lo necesario.
3. Si Windows muestra el aviso del Firewall, permite el acceso en **redes privadas**.
4. Para que arranque solo al iniciar sesión: doble clic en `autoinicio-windows.bat` (se quita con `quitar-autoinicio-windows.bat`).

### Mac
1. Si no tienes Python 3, abre Terminal y escribe `python3`: macOS ofrece instalar las herramientas de desarrollo. O instálalo desde https://www.python.org/downloads/.
2. Doble clic en **`iniciar.command`**. Si macOS lo bloquea (pasa cuando bajas el .zip): clic derecho → **Abrir**, o en Terminal `xattr -dr com.apple.quarantine .` dentro de la carpeta.
3. macOS pedirá dos permisos para Python. Acéptalos en *Ajustes del Sistema → Privacidad y seguridad* y reinicia Mando PC:
   - **Grabación de pantalla** (para ver la pantalla)
   - **Accesibilidad** (para mover el mouse y escribir)
4. Para que arranque solo al iniciar sesión: `./autoinicio-mac.command` (se quita con `./autoinicio-mac.command --quitar`).

### Emparejar el celular
Al arrancar se abre una página con un **código QR** (siempre disponible en http://localhost:8765/pair, solo desde esa laptop). Escanéalo con la cámara del iPhone, ábrelo en Safari y toca **Compartir → Agregar a inicio**.

La laptop debe estar **encendida**. Mientras Mando PC corre evita que se suspenda por inactividad (se puede desactivar con `"mantener_despierta": false`); si cierras la tapa, se suspende igual.

## Usarla fuera de casa (recomendado: Tailscale, gratis)

1. Instala **Tailscale** en la laptop y en el iPhone, e inicia sesión con la misma cuenta.
2. En `/pair` aparece un segundo QR "Tailscale". Escanéalo y agrégalo a inicio.

Funciona desde cualquier red sin abrir puertos en tu router. **No abras el puerto 8765 al internet.**

## Cómo se usa

| Pestaña | Qué hace |
|---|---|
| **Pantalla** | *Touchpad*: 1 dedo mueve, toque = clic, 2 dedos = scroll, toque con 2 dedos = clic derecho, toque + arrastre = arrastrar. *Tocar*: tocas donde quieres hacer clic. *Zoom*: pellizca para acercar. Botón **Teclado** para escribir en vivo. |
| **Teclado** | Escribir en vivo, texto largo, Ctrl/Alt/Shift/Win (⌘ en Mac), flechas, F1–F12, atajos, portapapeles de la laptop. |
| **Control** | Volumen, multimedia, tus atajos, abrir un enlace en la laptop, bloquear / suspender / reiniciar / apagar. Sensibilidad y calidad de imagen. |
| **Archivos** | Navega tus carpetas, descarga al celular, abre en la laptop, sube archivos. |

Los atajos y teclas se adaptan solos: en Mac usan ⌘ en lugar de Ctrl y los atajos por defecto son los de macOS.

## Seguridad

- Cada celular entra con un **token secreto** (192 bits) que solo aparece en `/pair`, que **solo abre desde la propia laptop**.
- Solo acepta conexiones de redes privadas (Wi-Fi local y Tailscale). Bloquea IPs que fallan muchas veces.
- Los archivos solo se ven dentro de las carpetas permitidas (por defecto tu carpeta de usuario).
- ¿Perdiste el celular? Ejecuta `iniciar.bat --nuevo-token` (Windows) o `./iniciar.command --nuevo-token` (Mac): invalida todos los celulares.
- Quien tenga la app emparejada controla la laptop; protege tu iPhone con Face ID/código.

## Configuración

Se guarda en `~/.mando-pc/config.json` (Windows: `C:\Users\TU_USUARIO\.mando-pc\config.json`; Mac: `/Users/TU_USUARIO/.mando-pc/config.json`). Ahí puedes cambiar el nombre que se muestra, el puerto, las carpetas visibles, la carpeta de subidas y tus **atajos**:

```json
{"nombre": "Abrir mi correo", "icono": "📧", "url": "https://mail.google.com"}
{"nombre": "Mostrar escritorio", "icono": "🖥️", "teclas": ["win", "d"]}
{"nombre": "Abrir Excel (Windows)", "icono": "📊", "ejecutar": "start excel"}
{"nombre": "Abrir Notas (Mac)", "icono": "📝", "ejecutar": "open -a Notes"}
```
Para cambiar el nombre de la laptop en la app: `"nombre": "Laptop oficina"`.

## Limitaciones conocidas

- Windows: no se ve ni controla la pantalla de bloqueo ni las ventanas de administrador (UAC) salvo que ejecutes Mando PC como administrador.
- Linux con Wayland no funciona; usa una sesión X11 (y `xclip` para el portapapeles).
- Si la laptop se apaga o se suspende, no hay forma de despertarla desde la app.
- Probado a fondo en Linux (X11). Los caminos de Windows y Mac usan las mismas librerías, pero conviene confirmarlos en tu equipo: si algo falla, el mensaje aparece en la app y en `~/.mando-pc/mando.log`.
