# Mando PC (connect-ai-qpp)

Controla tu laptop desde el celular: **pantalla en vivo, touchpad, teclado, volumen, bloquear/suspender/apagar y archivos** (bajar y subir).
Es una PWA (se instala en el iPhone como app) que habla con un programa pequeño que corre en tu laptop. No usa servidores de terceros ni cuentas: todo queda entre tu celular y tu laptop.

Funciona igual en **Windows y Mac** (y Linux con X11). Si usas las dos, instálala en cada una: cada laptop queda como una app distinta en tu iPhone, con su nombre ("Mando · MiLaptop").

## Instalación (una sola vez por laptop, ~3 min)

Descarga o clona este repo en la laptop y sigue los pasos de tu sistema.

> ⚠️ Si bajaste el **ZIP**, primero **extráelo** (clic derecho → *Extraer todo…*) y abre `iniciar` desde la carpeta nueva. Si lo abres dentro del ZIP falla con "requirements.txt not found".

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

### Vincular el celular (una vez por celular)
Al arrancar se abre una página con un **código QR** (siempre en http://localhost:8765/pair, solo desde esa laptop; también con `agregar-celular.bat` / `agregar-celular.command`).

1. Escanéalo con la cámara y ábrelo en Safari (iPhone) o Chrome (Android).
2. **Toca Compartir → Agregar a pantalla de inicio.** La app te lo recuerda mientras no lo hagas: sin esto, Safari borra la vinculación tras ~7 días sin uso.

Cada celular recibe **su propia llave**, no caduca y entra las veces que quiera sin volver a escanear. En `/pair` ves la lista de celulares vinculados y puedes **desvincular** uno sin afectar a los demás. El QR sirve una sola vez y vence en 15 minutos.

## Que la laptop siga disponible

| Situación | ¿Funciona? |
|---|---|
| Pantalla apagada por inactividad | Sí |
| Laptop **bloqueada** (Win+L o por tiempo) | El programa sigue corriendo, pero **no se puede ver ni teclear la contraseña** en la pantalla de bloqueo (lo impide el sistema). La app muestra un aviso 🔒. |
| Suspendida, hibernada, apagada o tapa cerrada | No: no hay forma de despertarla desde la app |

Para trabajar a distancia sin sorpresas, ejecuta **una vez** `modo-remoto-windows.bat` (o `modo-remoto-mac.command`): con la laptop conectada a la corriente no se suspende, cerrar la tapa no la duerme y no pide contraseña al despertar. Se deshace con el argumento `quitar`. Para que Mando PC arranque solo al iniciar sesión: `autoinicio-windows.bat` / `autoinicio-mac.command`.

## Usarla fuera de casa (Tailscale, gratis)

1. Instala **Tailscale** en la laptop y en el iPhone e inicia sesión con la misma cuenta (`modo-remoto-windows.bat` puede instalarlo por ti). Deja la VPN de Tailscale activada en el iPhone.
2. Recarga `/pair`: aparece un QR **Tailscale** (recomendado). Escanéalo y agrégalo a inicio.

Usa **ese** QR también para el uso diario: la app queda atada a la dirección con la que la instalaste, y la de Tailscale funciona en casa y fuera. La del Wi-Fi solo sirve dentro de la red. No abras el puerto 8765 al internet.

## Cómo se usa

| Pestaña | Qué hace |
|---|---|
| **Pantalla** | *Touchpad*: 1 dedo mueve, toque = clic, 2 dedos = scroll, toque con 2 dedos = clic derecho, toque + arrastre = arrastrar. *Tocar*: tocas donde quieres hacer clic. *Zoom*: pellizca para acercar. Botón **Teclado** para escribir en vivo. |
| **Teclado** | Escribir en vivo, texto largo, Ctrl/Alt/Shift/Win (⌘ en Mac), flechas, F1–F12, atajos, portapapeles de la laptop. |
| **Control** | Volumen, multimedia, tus atajos, abrir un enlace en la laptop, bloquear / suspender / reiniciar / apagar. Sensibilidad y calidad de imagen. |
| **Archivos** | Navega tus carpetas, descarga al celular, abre en la laptop, sube archivos. |

Los atajos y teclas se adaptan solos: en Mac usan ⌘ en lugar de Ctrl y los atajos por defecto son los de macOS.

## Seguridad

- Cada celular entra con **su propio token secreto** (192 bits) que se entrega con un QR de un solo uso desde `/pair`, que **solo abre desde la propia laptop**.
- Solo acepta conexiones de redes privadas (Wi-Fi local y Tailscale). Bloquea IPs que fallan muchas veces.
- Archivos: por defecto ves **todo el disco** (todas las unidades). Para limitarlo pon `"acceso_total": false` y lista las carpetas en `"carpetas"`.
- ¿Perdiste un celular? Desvincúlalo en `/pair`. ¿Quieres borrarlos todos? `iniciar.bat --nuevo-token` (Windows) o `./iniciar.command --nuevo-token` (Mac).
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

- Windows/Mac: no se ve ni controla la pantalla de bloqueo ni (en Windows) los avisos de permisos (UAC) salvo que ejecutes Mando PC como administrador.
- Linux con Wayland no funciona; usa una sesión X11 (y `xclip` para el portapapeles).
- Si la laptop se apaga o se suspende, no hay forma de despertarla desde la app (usa el modo remoto para evitarlo). Tras reiniciar, Windows/Mac esperan que inicies sesión antes de que Mando PC arranque.
- Probado a fondo en Linux (X11). Los caminos de Windows y Mac usan las mismas librerías, pero conviene confirmarlos en tu equipo: si algo falla, el mensaje aparece en la app y en `~/.mando-pc/mando.log`.
