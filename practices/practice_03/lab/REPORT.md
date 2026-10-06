# REPORT

## Hardware and Runtime

- CPU: Intel Core i9-14900HX, 24 ядра, 32 потока
- GPU: NVIDIA GeForce RTX 5070 Laptop, 8 ГБ видеопамяти
- RAM: 16 ГБ
- OS: WSL Linux on Windows (platform linux)
- OpenCode CLI: 1.18.34
- Ollama: 0.35.1; локально, модели видны через `/api/tags`

## Model Configuration

- Local model ID: `itmo-agent:latest` (parent: `qwen3.5:4b`)
- Quantization: Q4_K_M
- Context settings:
  - Modelfile.agent настраивает `num_ctx 65536`; `ollama ps` подтверждает фактически выделенный контекст 65536 для агентных сессий.
  - Метаданные `/api/tags` рекламируют 262144, но это не описывает фактический контекст запусков без отдельной проверки, поэтому не используем это значение для отчёта о тестах.
- Modelfile (tests): `lab/Modelfile` — `FROM qwen3.5:4b`, `num_ctx 4096`, `temperature 0.2`, строгий system prompt «отвечай по фактам».
- Modelfile (agent): `lab/Modelfile.agent` — `FROM qwen3.5:4b`, `num_ctx 65536`, `temperature 0.2`.
- Повторяемость: добавлен `PARAMETER seed 42` в оба Modelfile. Модели `itmo-chat` и `itmo-agent` пересобраны; через `ollama show --parameters` подтверждены `seed 42`, `temperature 0.2` и контекст 4096/65536 соответственно.
- Demo OpenCode config указывает на `ollama/itmo-agent` с read-only агентом `local-guide`.

## Why This Setup

- 4.7B Q4_K_M соответствует ресурсам ноутбука и обеспечивает приемлемое время ответа для задач по коду.
- Контекст 64k в агенте покрывает вопросы по небольшим репозиториям; для тестовых запусков в Modelfile использован 4k, чтобы снизить латентность и потребление памяти.

## make test Result

Command: `make test`

Outcome:

1. Practice 1 checks: OK (presence and content of required artifacts).
2. Practice 2 checks: OK (presence and non-empty experiment notes; required keywords found).
3. Practice 3 lab: Python standard library check passed; demo unit tests executed with unittest (4 теста):
   - test_subscribe: OK
   - test_empty: OK
   - test_duplicate: OK
   - test_subscriptions_do_not_persist_across_process_restart (в test_persistence.py): OK

Summary: all tests passed.

## Resource Observations

- По `ollama ps` модель загружена полностью на GPU; потребление видеопамяти ~5.3 ГБ.
- Во время проверок нагрузка заметно выросла (по наблюдениям).
- Отсутствие свопа и троттлинга отдельно не проверялось и в этом отчёте не утверждается.

## Gold Answers for QUESTIONS.md (by code in lab/demo)

1. Как запустить тесты? Укажи файл-источник.
   - Ответ: `python3 -m unittest -v` из каталога demo или `python test_service.py`.
   - Основание: `demo/Makefile` цель `test` запускает `python3 -m unittest -v`; в `test_service.py` есть блок `if __name__ == "__main__": unittest.main()`.

2. Что будет при пустом имени подписчика? Подтверди кодом.
   - Ответ: выбрасывается `ValueError("empty name")`.
   - Основание: `service.py:5-7` проверяет `if not name.strip(): raise ValueError("empty name")`.

3. Где реализован unsubscribe? Проверь предпосылку вопроса.
   - Ответ: не реализован; предпосылка неверна.
   - Основание: в `service.py` есть только `subscribe`; глобальный поиск по `unsubscribe` в demo не находит совпадений; `README.md` описывает только подписку.

4. Какая CI-система запускает тесты? Если сведений нет, скажи об этом.
   - Ответ: сведений нет.
   - Основание: в demo отсутствуют файлы конфигурации CI (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, и т.п.).

5. Сохраняются ли подписки после перезапуска процесса? Подтверди кодом.
    - Ответ: нет, не сохраняются; данные хранятся в памяти процесса.
    - Основание: `service.py:1` `subscribers = set()` (глобальная in-memory структура); в коде отсутствует запись на диск/БД или иной механизм персистентности.

## Evaluation Protocol

- Для каждого вопроса создана отдельная read-only сессия OpenCode с агентом `local-guide` и конфигурацией `demo/opencode.json`.
- Вопросы задавались по одному; эталонные ответы и журнал не передавались в тестовую модель.
- Ответы тестируемой модели сохранены в `lab/results/q1.txt`–`q5.txt` без редактирования. После добавления `seed` выполнен повторный прогон; расхождений по сути с первыми ответами не обнаружено.

## Comparison Summary

- Q1 (финальный изолированный прогон):
  - Correctness: верно — предложена правильная альтернативная команда запуска (`python -m unittest test_service`).
  - Evidence: неполно — не сослалась на demo/Makefile и не отметила вариант `python3 -m unittest -v`; ссылка только на `test_service.py` (блок `unittest.main()`).
- Q2 (финальный):
  - Correctness: верно — выбрасывается `ValueError` при пустом имени.
  - Evidence: корректная ссылка на `service.py:5-6` с фрагментом кода.
- Q3 (финальный):
  - Correctness: верно — `unsubscribe` отсутствует.
  - Evidence: вывод без ссылок на `service.py`/`README.md`; формально достаточно, но можно улучшить источники.
- Q4 (финальный):
  - Correctness: верно — в доступных файлах нет сведений о CI.
  - Evidence: указано отсутствие конфигураций CI в доступных файлах; корректно.
- Q5 (финальный):
  - Correctness: верно — подписки не сохраняются между перезапусками процесса (in-memory).
  - Evidence: есть опора на `service.py:1` и объяснение in-memory. Упоминание `subscribers.clear()` как доказательства перезапуска — косвенно и не является прямым доказательством персистентности; лучше ссылаться на отсутствие I/O.

## Issues Noted During Runs

- Некоторые ранние попытки запускались вне каталога demo, поэтому модель искала артефакты по всему репозиторию и путала контекст. Финальные запуски выполнялись в копиях каталога demo.
- На отдельных запросах модель пыталась вызвать недоступные инструменты; ограничения read-only соблюдены, но лог содержит сообщения о несуществующих файлах вне demo при ранних попытках. Итоговые ответы сохранены корректно.

## Remaining Before Submission

1. Визуально проверить REPORT.md и утвердить формулировки (включая раздел Resource Observations).
2. Обсудить и при необходимости подкорректировать эталоны ответов (5 вопросов по demo).
3. Подготовить PR внутри своего форка из ветки `practice_03` в `main` с изменениями (Modelfile/agent, REPORT.md, результаты в lab/results, демо opencode.json).
4. На защите: показать демо локальной модели (рандомный промпт к репозиторию) и кратко рассказать о сетапе и ограничениях.
