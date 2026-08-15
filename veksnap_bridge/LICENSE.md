# veksnap_bridge licensing

This ComfyUI extension package is split into two parts with different licensing,
to keep Vek-Snap™'s proprietary code cleanly separated from GPL ComfyUI:

- **`__init__.py`**: declares only `WEB_DIRECTORY` (a data hook ComfyUI reads).
  It imports nothing from ComfyUI and registers no server routes, so it is **not
  a derivative work** of ComfyUI. No copyleft obligation attaches to it.

- **`web/veksnap_open_workflow.js`**: the only file that uses the ComfyUI
  front-end API (`app.loadApiJson`, etc.). It is therefore licensed under the
  **GNU General Public License v3.0 or later (GPL-3.0-or-later)**, matching
  ComfyUI. It contains no Vek-Snap proprietary logic. The full GPL-3.0 text is
  shipped at `../veksnap_utils/LICENSE-GPL-3.0.txt` and at
  <https://www.gnu.org/licenses/gpl-3.0.txt>.

The actual workflow relay (stash/serve) lives in the Vek-Snap application at
`/api/veksnap-bridge/open-workflow`, outside ComfyUI and outside this package.
