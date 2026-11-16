# Froja Library Studio (private prototype)

An original, local-only Froja plugin for indexing generated images. It does not
contain CyberHub code, assets, branding, data, or interface components.

## Safety boundaries

- Binds to `127.0.0.1` only.
- Never deletes, renames, moves, or copies source images.
- Stores only paths, searchable metadata, favorites, and collections.
- Does not scan a folder until it is explicitly configured.
- Does not contact the internet.
- Can be removed by deleting this plugin folder; Froja Core is unchanged.

## Run privately

```powershell
python library_service.py --folder "G:\ComfyUI_NEW\output\Froja"
```

Open `http://127.0.0.1:9020`. Additional folders can be supplied with repeated
`--folder` arguments. The index is stored in `data/library.sqlite3`.

## API

- `GET /api/status`
- `POST /api/scan`
- `GET /api/images?q=...&favorite=1&collection=...`
- `GET /api/image?id=...`
- `POST /api/favorite` with `{ "id": 1, "favorite": true }`
- `GET /api/collections`
- `POST /api/collections` with `{ "name": "Portraits" }`
- `POST /api/collection-items` with `{ "image_id": 1, "collection_id": 1 }`
- `GET /api/reuse?id=...`

