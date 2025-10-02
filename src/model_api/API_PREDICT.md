## POST /predict — описание API

- **URL**: `http://<backend-host>:8000/predict`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Query params**:
  - `threshold` (optional, float, default `0.5`): порог для бинарных предсказаний

### Form-data поля
- **bpm**: файл FHR, CSV/XLSX. Две колонки: time (0), value (1)
- **uterus**: файл Uterus, CSV/XLSX. Две колонки: time (0), value (1)

### Успешный ответ (200)
```json
{
  "labels": ["кесарево сечение", "..."],
  "predictions": {
    "кесарево сечение": {"proba": 0.123, "pred": 0},
    "...": {"proba": 0.456, "pred": 1}
  }
}
```

### Ошибки
- 400: неверный формат файла / меньше 2 колонок / нет валидных чисел
- 500: внутренняя ошибка инференса

### Пример cURL
```bash
curl -X POST "http://localhost:8000/predict?threshold=0.5" \
  -F "bpm=@/path/to/fhr.csv" \
  -F "uterus=@/path/to/uterus.csv"
```

### Пример fetch (браузер)
```javascript
async function uploadAndPredict(bpmFile, uterusFile, threshold = 0.5) {
  const form = new FormData();
  form.append('bpm', bpmFile);
  form.append('uterus', uterusFile);

  const res = await fetch(`${import.meta.env.VITE_API_URL}/predict?threshold=${threshold}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

### Заметки по CORS и продакшену
- CORS включён в бэкенде. В проде настройте `allow_origins` на конкретные домены фронтенда.
- Ограничивайте размер загрузки через reverse-proxy (nginx) и используйте HTTPS.


