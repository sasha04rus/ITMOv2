# Независимая проверка логики и HTTP-контракта

Проверяющий: агент команды UI (`/root/practice05_ui`), который не писал `app/service.py`, `app/server.py` и Python-тесты. Собственный слой UI в эту проверку не включён. Реализация, спецификации и Git не изменялись; создан только этот отчёт.

Основание: [утверждённый общий контракт](../specs/001-subscriber-search/contracts/http.md).

## Фактический запуск

Рабочий каталог: `practices/practice_05` отдельного worktree `practice_05`.

Выполнена команда с bundled Python и разрешённым доступом к локальному HTTP:

```powershell
& 'C:/Users/Sasha Tastakov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -v
```

Фактический результат этой независимой проверки:

```text
Ran 23 tests in 0.820s

OK
```

Код завершения: `0`. Проверка не ограничивалась чтением отчёта автора: тесты реально запущены, HTTP-тесты открывали сервер на `127.0.0.1` с динамическим портом, а CLI-тест запускал отдельные процессы сервера с `--demo` и без него.

## Критерий -> ожидание -> факт -> доказательство

| Критерий | Ожидание по контракту | Фактический результат | Доказательство |
|---|---|---|---|
| Полный список | Отсутствующий `q`, `q=` и запрос из пробелов возвращают весь отсортированный список | Пройдено: HTTP 200; `query` пуст; Alice, Bob, Анна, Борис; `total=4` | [test_full_list_missing_and_empty_q](../tests/test_http.py#L75), [test_search_utf8_and_normalized_query](../tests/test_http.py#L82) |
| Регистр и русский язык | `  ALI  ` находит Alice, `АН` находит Анна; написание имён сохраняется | Пройдено на уровне функции и настоящего HTTP; `query` после trim сохраняет регистр | [test_latin_and_cyrillic_substrings_ignore_case](../tests/test_service.py#L49), [test_search_utf8_and_normalized_query](../tests/test_http.py#L82), [search_subscribers](../app/service.py#L52) |
| Python Unicode trim | Нормализация соответствует `str.strip()`, а не отдельному правилу браузера | Пройдено для U+001C и U+2003; HTTP-сценарий также включает U+001C | [test_unicode_strip_matches_python_rules](../tests/test_service.py#L54), [test_search_utf8_and_normalized_query](../tests/test_http.py#L82), [normalize_query](../app/service.py#L39) |
| Пустой результат | Нет совпадений или подписчиков — HTTP 200, пустой `items`, `total=0` | Пройдено; пустое состояние не превращается в 404/400 | [test_no_match_and_empty_storage_are_successful](../tests/test_service.py#L63), [test_empty_storage](../tests/test_http.py#L95) |
| Граница 100/101 | Длина измеряется в Unicode code points после strip; 100 допустимы, 101 дают `400 query_too_long` | Пройдено для букв и emoji; после ошибки следующий корректный HTTP-запрос проходит | [test_100_code_points_accepted_and_101_rejected](../tests/test_service.py#L75), [test_code_point_boundary_and_recovery](../tests/test_http.py#L101) |
| Порядок нормализации | Лимит проверяется после strip и до расширения casefold | Пройдено: 100 символов `ß`, окружённых пробелами, принимаются и находят исходное имя | [test_length_checked_after_strip_before_casefold](../tests/test_service.py#L83), [normalize_query](../app/service.py#L39) |
| Определённые границы поиска | Unicode casefold, но без транслитерации, е/ё-эквивалентности и NFC-нормализации | Пройдено: STRASSE находит Straße; `ел` не находит Ёлка; декомпозированное `e\u0301` не совпадает с `é`; `anna` не находит Анна | [test_casefold_without_transliteration_or_accent_normalization](../tests/test_service.py#L88) |
| Ошибочная структура URL | Повторный `q`, неизвестный параметр и некорректный UTF-8 дают `400 invalid_query` | Пройдено для повторов, неизвестных ключей, `%`, `%GG`, `%FF`, overlong UTF-8 и кодирования surrogate | [test_unknown_duplicate_and_malformed_query](../tests/test_http.py#L117), [parse_query](../app/server.py#L23) |
| Форма и кодирование ответа | `query` строка, `items` массив строк, `total=items.length`; JSON UTF-8 | Пройдено: тесты сравнивают полные объекты, Content-Type и Content-Length; кириллица декодируется корректно | [request_json и HTTP-проверки](../tests/test_http.py), [_json](../app/server.py#L66), [do_GET](../app/server.py#L73) |
| Методы и неизвестные маршруты | POST/PUT/PATCH/DELETE API дают 405; неизвестный маршрут — 404 | Пройдено; код `method_not_allowed`, заголовок `Allow: GET`; неизвестные маршруты дают `not_found` | [test_unsupported_api_methods](../tests/test_http.py#L124), [test_unknown_routes_and_traversal_not_served](../tests/test_http.py#L140), [_unsupported_method](../app/server.py#L101) |
| Выдача статики | Доступны только `/`, `/app.js`, `/style.css`; произвольные файлы не выдаются | Пройдено для allowlist, MIME-типов и нескольких traversal/служебных путей | [test_static_allowlist_and_content_types](../tests/test_http.py#L132), [test_unknown_routes_and_traversal_not_served](../tests/test_http.py#L140), [STATIC_FILES](../app/server.py#L15) |
| Поиск не меняет данные | Возвращается новый список; прежнее множество сохраняется | Пройдено: изменение/очистка результата не влияет на хранилище | [test_search_result_is_independent_and_storage_unchanged](../tests/test_service.py#L68), [test_list_sorted_and_independent](../tests/test_service.py#L31) |
| Регрессия прежних операций | Trim, запрет пустых имён, точные дубликаты, True/False при отписке и прежняя сортировка сохраняются | Все четыре регрессионных теста пройдены; Ann и ann остаются различными именами в хранилище | [SubscriptionRegressionTests](../tests/test_service.py#L6), [subscribe/unsubscribe/list_subscribers](../app/service.py#L16) |
| Явное включение демо | Без флага — пусто; `--demo` — четыре имени | Пройдено в двух настоящих отдельных CLI-процессах; URL с фактически выделенным портом рабочий | [test_actual_port_url_and_explicit_demo_flag](../tests/test_http.py#L156), [main](../app/server.py#L132) |
| HTML-подобные имена в API | Имя остаётся JSON-данными с исходным текстом | Пройдено для `<img src=x onerror=alert(1)>`; API возвращает точную строку | [test_api_returns_name_as_json_data](../tests/test_http.py#L147) |

## Найденные проблемы

В проверенных границах конкретных нарушений утверждённого контракта не обнаружено. Все 23 теста завершились успешно. Код поиска и сервер прочитаны непосредственно; вывод основан на тестах и коде, а не на пересказе автора.

## Пределы этой проверки

- Браузерный сквозной сценарий здесь не запускался. Вывод API с HTML-подобным именем не доказывает безопасную вставку в DOM; это отдельная проверка UI.
- HTTP-тест статики использует временные fixture-файлы, поэтому подтверждает маршрутизацию и MIME-типы сервера, но не качество настоящих HTML/CSS/JS.
- Отображение loading/error/empty, повтор последнего запроса, клавиатура и защита от устаревших ответов относятся к отдельной проверке UI.
- Нагрузочная работа, многопользовательские операции записи и персистентность не проверялись: они не входят в согласованную фичу.

Результат: логика и HTTP-слой проходят независимую проверку согласованных основных, ошибочных, граничных и регрессионных сценариев. Приёмка человеком и браузерные доказательства фиксируются отдельно.
