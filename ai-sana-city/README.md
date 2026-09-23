# AI Sana · Город решений

Flask/Jinja2-версия исходного самодостаточного прототипа. Визуальная часть и клиентское поведение перенесены без смысловых изменений; данные зданий, миссии, магазина, коллекции и финальных критериев задаются Python-моделями.

## Требования

- Python 3.11 или новее
- Доступ в интернет при первом открытии страницы для загрузки Google Fonts

## Запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app app run
```

Откройте <http://127.0.0.1:5000>.

## API

- `GET /api/buildings`
- `GET /api/missions/support-rescue`
- `POST /api/criteria/<id>/toggle`
- `POST /api/hints/<step_id>/next`

Состояние демонстрационных POST-маршрутов хранится в памяти процесса и сбрасывается при перезапуске сервера.
