# GitHub Spec Kit: применение и сравнение с OpenSpec

## Что применено

Для ДЗ выбран **GitHub Spec Kit**, а не OpenSpec из аудиторной части.
Официальный источник: https://github.com/github/spec-kit.
Использована версия исходников `1.2.4.dev0`, закреплённая коммитом
`9783b49ed66c26935cf7ef5ccc6ae5a296316eb7`; provenance сохранён в
`evidence/spec-kit-source.json`. Это версия из зафиксированного исходного кода,
а не утверждение о последнем стабильном релизе.

CLI установлен в отдельное локальное окружение и реально выполнен:

```text
specify version
specify init --here --force --non-interactive --integration opencode --script py --ignore-agent-tools --integration-options="--events false"
```

Результаты, включая exit codes, находятся в `evidence/spec-kit-cli.json`.
Инициализация выполнена внутри папки практики, не поверх настроек практик 3–4.
Сгенерированные команды `.opencode/commands/` предназначены для OpenCode.

В текущих двух агентных сессиях применены шаги Spec Kit: constitution → specify →
clarify → plan → tasks → implement → verification. Slash-команды — инструкции
для coding agent, а не отдельный генератор текста в терминале. Здесь агент
следовал установленным инструкциям и использовал официальную автоматизацию;
запуск OpenCode с платной моделью для этой работы не заявляется.

## Проверяемые артефакты по шагам

| Шаг | Фактическое применение |
|---|---|
| Constitution | `.specify/memory/constitution.md`: совместимость, границы, подтверждения |
| Specify | Два независимых черновика `specs/before/`, сводная feature spec по официальному шаблону |
| Clarify | `specs/coordination.md`: лимит 100/128, коды ошибок и неоднозначности; обновлены `after/` |
| Plan | `specs/001-subscriber-search/plan.md` и `contracts/http.md` |
| Tasks | Dependency-ordered `tasks.md` с идентификаторами и проверками |
| Implement | UI и Python-логика по утверждённому контракту |
| Verify | Unit, HTTP, браузер, отдельная проверка; результаты в `evidence/` |

Официальные Python-скрипты `create_new_feature.py`, `setup_plan.py`,
`setup_tasks.py` действительно запускались. Запись — `evidence/spec-kit-bootstrap.json`.
Каталог feature имеет имя `001-subscriber-search`; Git-ветка остаётся `practice_05`.
Это поддерживается выбранной версией, которая хранит активную feature отдельно
от Git-ветки. Воспроизводимая проверка на свежем checkout:

```bash
python3 scripts/check_spec.py
```

Обёртка задаёт актуальные пути и запускает официальный `check_prerequisites.py`.
Проверка наличия артефактов не заменяет тестирование требований.

## Сравнение с OpenSpec

Сравнение опирается на workflow OpenSpec из презентации курса и фактически
использованный Spec Kit; отдельный эксперимент запуска OpenSpec здесь не заявляется.

| Аспект | OpenSpec в материалах практики | Spec Kit в этой работе |
|---|---|---|
| Основной маршрут | Explore → propose → review → apply → проверки → sync/archive | Constitution → specify → clarify → plan → tasks → implement → verification |
| Центр организации | Change и его delta specs, затем обновление main specs | Feature spec, технический план, контракт и задачи |
| Правила проекта | config.yaml, context и rules | Конституция и шаблоны `.specify/` |
| Уточнение | Обсуждение и update change | Clarify и синхронизация двух спецификаций с общим контрактом |
| Роль CLI | Инструкции, статус и структурная validate | Инициализация, шаблоны и prerequisites |
| Роль модели | Создаёт содержание артефактов и код | Создаёт содержание артефактов и код |
| Роль человека | Решения до apply и приёмка до archive | Выбор фичи, решение по контракту до реализации, итоговая приёмка |

Для маленькой фичи полный Spec Kit добавляет немало служебных файлов. Практическая
польза здесь — явное разделение требований, технического решения и задач, плюс
контроль согласованности двух команд до появления кода. Ни один фреймворк сам
не гарантирует правильный поиск или корректный UI.

## Повторная установка инструмента, если потребуется

Приложение и обычные тесты работают без Spec Kit CLI. Официальные скрипты и
шаблоны уже сохранены. Для повторной установки той же версии в отдельное окружение:

```bash
python3 -m venv .venv-tools
.venv-tools/bin/python -m pip install 'git+https://github.com/github/spec-kit.git@9783b49ed66c26935cf7ef5ccc6ae5a296316eb7'
```

В Windows интерпретатор окружения находится в `.venv-tools/Scripts/python.exe`.
Сгенерированные Python-команды OpenCode могут содержать путь интерпретатора этой
машины: на другой машине повторите `specify init` или используйте переносимые
команды `python3 scripts/check_spec.py` и `python3 -m app.server --demo`.
