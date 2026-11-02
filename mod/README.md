# Modbucksot Telemetry r1

Первый модуль добавляет только JSONL-событие `turn_changed` в настоящий мультиплеер Buckshot Roulette `v2.2.0` (Steam build `16736575`).

## Применение

1. Создайте рабочую копию игры и восстановите её проект через GDRE Tools.
2. Запустите:

   ```powershell
   py mod\apply_telemetry_r1.py "C:\path\to\extracted\multiplayer\scripts\global scripts\MP_RoundManager.gd"
   ```

3. Соберите отдельный EXE через GDRE Tools, подменив в нём файл по пути `res://multiplayer/scripts/global scripts/MP_RoundManager.gd`.
4. Проверьте `user://modbucksot/events.jsonl` в ручном матче.

Применитель проверяет SHA-256 исходного `MP_RoundManager.gd` и завершится без изменений, если игра или восстановленный скрипт не совпадает с ожидаемой версией.

Запись содержит старый и новый сокеты, номер раунда и UTC-время. Код не отправляет сетевые пакеты и не меняет игровые значения.

Файлы Steam-установки и извлечённые игровые ресурсы исключены из Git.
