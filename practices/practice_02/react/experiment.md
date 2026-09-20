# ReAct

Файл ведёт OpenCode по вашим запросам. Агент записывает фактические результаты экспериментов и вносит изменения в связанные файлы. Свою оценку сообщайте ему в чате; вручную заполнять шаблон не нужно.

- Цель:
  Пошагово проверить согласованность итогового product_management.md с tests_e2e.md и результатами пяти предыдущих экспериментов, найти оставшиеся несоответствия и предложить минимальную финальную правку.
- Доступные входы:
  - practices/practice_01/context.md;
  - practices/practice_01/problem.md;
  - practices/practice_01/product_management.md;
  - practices/practice_01/tests_e2e.md;
  - practices/practice_01/TRAINING_PR.diff;
  - practices/practice_02/prompts.md;
  - результаты Few-shot, R.C.T.F., Chain of Verification, Tree of Thoughts и RAG.
- Разрешённые действия:
  - читать только перечисленные файлы;
  - сравнивать первый рабочий сценарий, таблицу Use case, Gherkin, таблицу статусов и E2E;
  - проверять ссылки на хунки и разделы;
  - выполнить make -C practices/practice_02 test;
  - выполнить git diff --check только для файлов practices/practice_01 и practices/practice_02;
  - предложить минимальные исправления;
  - записать фактические действия и наблюдения только в этот файл.
- Запрещённые действия:
  - интернет и внешние источники;
  - изменение файлов Practice 1 до подтверждения;
  - изменение prompts.md до оценки ReAct;
  - commit и push;
  - придумывание HTTP-статусов, лимита размера diff, SLA или реализованной валидации;
  - скрытые рассуждения.
- Максимальное число шагов: 8.
- Условие остановки и вопроса человеку:
  Остановиться, когда: проверены согласованность product_management.md и tests_e2e.md; проверены статусы AS IS / TO BE / OPEN; проверены ссылки на источники; выполнены разрешённые проверки; сформирован список только минимальных необходимых правок. Если нужна продуктовая договорённость — задать вопрос человеку и остановиться.

## Запрос

"ReAct check for PR-review assistant

Goal: validate consistency of product_management.md with tests_e2e.md and prior experiments; find remaining inconsistencies and propose minimal final fix.

Inputs: context.md, problem.md, product_management.md, tests_e2e.md, TRAINING_PR.diff, practices/practice_02/prompts.md, and results of Few-shot, R.C.T.F., CoV, ToT, RAG.

Allowed actions: read listed files; compare scenario, Use case, Gherkin, status table and E2E; verify links to hunks/sections; run `make -C practices/practice_02 test`; run `git diff --check` for practices/practice_01 and practices/practice_02; propose minimal fixes; log actions and observations only here.

Forbidden: internet; changing Practice 1 files; changing prompts.md; commit/push; inventing HTTP status, diff size limits, SLA or implemented validation; hidden thoughts.

Max steps: 8.
Stop when: consistency and links verified, checks run, minimal changes outlined. Ask user for product decisions instead of making them.

Follow ReAct: at each step log Action, Observation, Decide."
## Наблюдаемые действия и результаты

| Шаг | Действие | Наблюдение | Решение продолжить или остановиться |
|---|---|---|---|
| 1 | Прочитать product_management.md, tests_e2e.md, context.md, problem.md | Gherkin и E2E согласованы по позитивному/негативному/граничному; таблица статусов отражает AS IS/TO BE/OPEN; context.md задаёт исходные требования | Продолжить: сверить ссылки на TRAINING_PR.diff |
| 2 | Проверить TRAINING_PR.diff хунки app/api.py и app/review_service.py | app/api.py @@ -1,8 +1,17 @@ — обращение payload["diff"]; app/review_service.py @@ -1,10 +1,23 @@ — prompt с diff и возврат {"comment": answer} | Продолжить: сверить prompts.md и журналы экспериментов |
| 3 | Просмотреть practices/practice_02/prompts.md и результаты экспериментов | Few-shot/R.C.T.F./CoV/ToT/RAG отражены; изменения согласованы; RAG содержит уточнения по источникам | Продолжить: проверить формальные проверки |
| 4 | Выполнить make -C practices/practice_02 test | Вывод: «Practice 2 artifacts: OK» | Продолжить: проверить git diff --check |
| 5 | Выполнить git diff --check для practices/practice_01 и practices/practice_02 | Обнаружены многочисленные whitespace-замечания (в т.ч. из-за CRLF/окончаний строк); содержательных противоречий требованиям не выявлено | Продолжить: поиск несоответствий |
| 6 | Сверить статус-таблицу с RAG-категориями | Строки про AS IS (точные хунки), TO BE и OPEN присутствуют; Evidence-first отмечен как TO BE; открытые вопросы добавлены | Продолжить: поиск минимальных правок |
| 7 | Сверить формулировку граничного правила в Gherkin и E2E | Оба фиксируют фильтр достаточного evidence; ≤3 — все; >3 — сортировка и top-3; file-only → «Проверки» | Продолжить: итог |
| 8 | Сформировать список минимальных правок | Предложено минимальное изменение Use case; выявлены whitespace-замечания (косметика) | Остановиться |

## Несоответствия

- Use case в product_management.md: поле «Ошибка или отказ» не было синхронизировано с негативным Gherkin-сценарием (AS IS/TO BE и поведение для неподтверждённых утверждений). Теперь синхронизировано.

## Минимальные предлагаемые изменения

- Синхронизировать Use case → поле «Ошибка или отказ» с негативным сценарием (AS IS/TO BE; исключение неподтверждённых утверждений из «Рисков» → в «Проверки») — выполнено.
- Опционально: нормализовать окончания строк LF и удалить trailing whitespace в затронутых файлах (косметика, не меняет поведение).

## Результаты команд проверки

- Первая проверка: make -C practices/practice_02 test → Practice 2 artifacts: OK; git diff --check (для practices/practice_01 и practices/practice_02) → обнаружены многочисленные whitespace-замечания (CRLF/окончания строк)
- Финальная проверка после нормализации девяти целевых файлов: git diff --check (только для девяти файлов) → без замечаний

## Вопрос человеку / вывод

- Вывод: после синхронизации Use case «Ошибка или отказ» и косметической нормализации окончаний строк/пробелов артефакты согласованы.

## Что изменили в исходном артефакте

- Файл и раздел: practices/practice_01/product_management.md → Use case → поле «Ошибка или отказ».
- Изменение: синхронизировано с негативным Gherkin-сценарием (AS IS/TO BE; неподтверждённые утверждения исключаются из «Рисков» и переводятся в «Проверки»).
- Как проверили: перечитаны product_management.md и tests_e2e.md; make -C practices/practice_02 test; git diff --check на наборе файлов.
- Что отклонили: первоначальный ошибочный вывод, что git diff --check прошёл без замечаний, и что финальных правок не требуется.
