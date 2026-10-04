# Контракт расширенной модели

OpenDoc 0.2.0 расширяет общую модель документа типизированными данными и
операциями, независимыми от внешних форматов и приложений. API описан в
[руководстве](../guide/integration.md); реализация находится в
[типах](../../src/opendoc/integration_types.py) и
[операциях](../../src/opendoc/integration.py). Обязательные зависимости и
версии сохранённого документа не изменены.

| Область | Реализация и границы |
| --- | --- |
| Профили возможностей и сохранение | FeatureCapability, CapabilityProfile, PreservationRecord; существующие DiagnosticIssue/CheckResult/Provenance; неполный отчёт не подтверждает lossless |
| Исходные позиции и неизвестные фрагменты | SourceMap/File/Span/Mapping, ссылки раскрытий, digest, UnknownFragment с resource ID, media type и конечным размером |
| Поля и диапазоны | Существующие Anchor ID, TextPosition/Range, Field/BibliographyEntry, Comment/Revision/ContentControl; Unicode-редактирование и проверка ссылок |
| Векторные данные | Paths/Paint/AffineTransform/Groups/clip/mask/z-order, пункты и ColorValue; арность, конечные числа, циклы и бюджеты |
| Диаграммы и стили | Chart/Series/Axis, Diagram, явное наследование SceneStyle и отдельный visual fallback |
| Страницы и дополнительные данные | Pages/reading order/accessibility, annotations/forms, inert actions, media/timing; Workbook/Sheet/Cell отдельно от Table |
| Структура математики | FormulaTree/MathNode рядом с существующей Formula и исходными ресурсами; арность, глубина и число узлов |
| Развитие схем | Explicit consumer ExtensionMigration, forward chains, schema validation, atomic failure, feature negotiation, unknown-field preservation |

Данные подключены к существующим JSON-конвертам и валидации. Дополнительная
схема имеет собственную версию 1; JSON документа продолжает записываться в версии
2 и читаться в версиях 1 и 2. `Block` включает Paragraph, Table, Formula и Image;
новые произвольные типы структурных узлов не вводятся.

Проверки находятся в [корпусе](../../tests/test_integration.py): восстановление
JSON, Unicode и cross-run ranges, исходные spans, зависимости при извлечении,
переназначение IDs при объединении, повреждённые ссылки, циклы, неизвестные версии,
квоты и отсутствие частичных изменений.
[Пример](../../examples/integration_model.py) исполняется проверкой сайта и
установленным wheel без зависимостей. Сохранённые контракты API и JSON 0.1.0
остаются отдельными проверками совместимости.

## Назначение и пределы

Библиотека хранит, изменяет, сериализует и проверяет структуры в памяти. Конечная
схема задаёт общий носитель данных и не гарантирует чтение полного стандарта
документа. Чтение внешних файловых форматов, вычисление формул, поля, actions,
отрисовка, OCR, UI и редакторская история находятся вне API ядра.

Неподдержанные команды и исходные байты сохраняются через PackageGraph, Resource,
UnknownFragment или extra. Сохранение непрозрачных данных не означает понимание
их семантики. Профили и отчёты описывают заявленный охват потребителя. Библиотека
не выполняет скрипты, макросы, формулы и команды из сохранённых данных, не
открывает URI автоматически и не подключает внешние движки.
