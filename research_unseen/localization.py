"""Interface strings only; dialogue and game variable names are never translated."""

ANNOTATIONS = {
    'Выбор: ': 'Choice: ',
    '[доступен при ': '[available when ',
    'Вложенный пользовательский оператор': 'Nested custom statement',
    'Изменение камеры/слоя не восстанавливается.': 'Camera/layer changes are not restored.',
    'Перед репликой есть Python-вызов; его побочные эффекты не воспроизводятся.': 'A preceding Python call has side effects that are not replayed.',
    'Пользовательские экраны сцены не восстанавливаются.': 'Custom scene screens are not restored.',
}

TEXT = {
    'title': ('Unseen dialogue', 'Исследование пропусков'),
    'previous': ('Previous', 'Назад'),
    'next': ('Next fragment', 'Следующий фрагмент'),
    'hide': ('Hide', 'Скрыть'),
    'visual': ('Unknown background: blank frame', 'Фон неизвестен: пустой кадр'),
    'music': ('Unknown music: silence', 'Музыка неизвестна: тишина'),
    'errors': ('Some media could not be restored; see log.txt', 'Часть оформления не восстановлена; подробности в log.txt'),
    'end': ('No more fragments in this direction. Refresh the report after playing.', 'Больше фрагментов в этом направлении нет. Обнови отчёт после прохождения.'),
}


def translate_annotation(value, language):
    if language == 'en':
        for source, target in ANNOTATIONS.items():
            value = value.replace(source, target)
    return value


def ui_text(key, language='en'):
    return TEXT[key][language == 'ru']
