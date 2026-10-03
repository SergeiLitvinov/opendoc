# OpenDoc

Независимая Python-библиотека структур документов: пакет `opendoc`, импорт `opendoc`, Python 3.11+.

Модель, свойства, геометрия, цвета, ресурсы, формулы, обход и изменения, объединение/извлечение с зависимостями, JSON-сериализация, валидация и сравнение структуры работают самостоятельно. Обязательных внешних зависимостей нет. Дополнение `math` предоставляет `lxml` для сравнения поддержанного MathML/Office Math. Без него непроверяемая формула диагностируется, строгий допуск не считается соблюдённым.

```python
from opendoc import DocumentModel, Paragraph, Section, TextRun, load_document, save_document

document = DocumentModel(sections=[Section(blocks=[Paragraph(content=[TextRun("Мой документ")])])])
save_document(document, "document.json")
restored = load_document("document.json")
assert restored.validate() == []
```

Сборка из каталога OpenDoc: `uv build --out-dir dist`. Полученный wheel можно установить в другом проекте через `uv pip install путь/к/opendoc-0.1.0-py3-none-any.whl`. Публикация в реестр пока не выполнялась.

JSON сохраняет идентификатор `opendoc.document` и версию 2, читает версию 1. Версии пакета и JSON независимы. Дополнительные ключи `properties` и `metadata` сохраняются; неизвестные версии и типы блоков отклоняются. Это не обещание чтения произвольной будущей схемы без миграции.

Обработчики прикладных форматов, миграции прежних форматов приложений, шаблоны, задачи, CLI и web принадлежат потребителям. Библиотека работает без редактора; его интерфейс, сеансы и история отмены относятся к отдельному приложению. Чтение JSON сохраняет ресурсы без автоматического преобразования прикладных ролей в пакет OOXML.

Разработка: `uv sync --all-extras`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`.

[Руководство](docs/guide/index.md) · [API](docs/reference/api.md) · [Навигатор по коду](docs/reference/code.md) · [План](TODO.md).

[Свойства и стили](docs/guide/styles.md): строгие чтение/запись известных полей и независимый эффективный стиль с разрешением наследования.

[Ресурсы и переносимость](docs/guide/resources.md): явные конфликты ID, поиск использований и одинаковых данных, замена/удаление и встраивание локальных файлов на копии.

[Проверка в памяти](docs/guide/checks.md): структурированные ошибки и сравнение с явными политиками без выходного пути и обращений к внешним файлам.

Документация: `uv run python -m tools.docs generate`, затем `uv run python -m tools.docs check`. Локальный сайт: `uv run python -m tools.docs serve`, адрес http://127.0.0.1:8003/. [Как устроена автоматизация](docs/development/documentation.md).

[Стандарты кодирования](CODING_STANDARDS.md) проверяются lint и форматированием в CI.
