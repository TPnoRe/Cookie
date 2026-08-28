"""Defaults — ค่าเริ่มต้นของทุก config (จะถูก merge กับค่าที่โหลดจากไฟล์)."""

DEFAULT_SETTINGS = {
    'emulator': 'Auto Detect',
    'farm_mode': 'farm_box',
    'jump_interval': '0.80',
    'click_delay_min': '0.05',
    'click_delay_max': '0.15',
    'click_hold': '0.10',
    'click_jitter_pct': '0.2',
    'click_jitter_px': '0.5',
    'fast_start': True,
    'fast_start_delay': '1.0',
    'cookie_relay': True,
    'relic_check': True,
    'random_boost': True,
    'target_buff': 'Double Coins',
    'coord_mode': 'frame',
    'buff_list': [
        'Double Coins', '15% Score Bonus', '-15% HP drain',
        'Revive once with 80 HP', '70% Crush Chance', '+17% base speed',
        'Gold Coin Magic', '30% Collision Damage', '20% HP From Potions',
        'Magnetic Aura', '2 Pit Lifts',
    ],
}

DEFAULT_COORDINATES = {
    'lobby': [
        ['Play Button', 74.3, 89.6, 14.0, 8.0],
        ['Relic Diamond', 40.5, 15.5, 9.3, 6.8],
        ['Claim Relic', 50.0, 75.0, 15.0, 8.0],
        ['Confirm Relic', 50.0, 80.0, 15.0, 8.0],
        ['Close Relic', 50.0, 88.0, 15.0, 8.0],
        ['Heart', 70.6, 4.7, 7.8, 5.1],
        ['Close News', 84.2, 9.3, 8.0, 10.0],
        ['Close Event', 84.2, 9.3, 8.0, 10.0],
        ['Daily OK', 50.0, 90.7, 18.0, 12.0],
        ['Daily Confirm', 50.0, 69.6, 20.0, 12.0],
        ['League Confirm', 50.0, 64.29, 27.06, 11.43],
    ],
    'prep': [
        ['Random Boost', 41.3, 82.8, 6.8, 13.6],
        ['Start Game', 69.9, 85.2, 30.0, 12.0],
        ['Boost Scan', 85.4, 27.4, 7.2, 10.6],
        ['Multi Buy', 49.8, 82.0, 17.0, 7.7],
        ['SelectFo', 68.4, 75.4, 25.8, 5.3],
        ['Template Prep', 21.6, 15.9, 18.1, 5.5],
        ['Select Fast Start', 17.5, 82.8, 8.8, 11.0],
        ['Buy Fast Start', 70.4, 41.0, 7.8, 7.3],
        ['Select Cookie Relay', 31.3, 82.8, 8.8, 11.0],
        ['Buy Cookie Relay', 70.4, 41.0, 7.8, 7.3],
    ],
    'gameplay': [
        ['Jump', 12.9, 86.8, 11.1, 7.3],
        ['Slide', 88.1, 87.0, 11.1, 7.0],
        ['Fast Start', 50.5, 47.3, 8.3, 9.5],
        ['Cookie Relay', 50.0, 50.0, 10.0, 8.0],
    ],
    'results': [
        ['Open All', 50.0, 89.4, 13.2, 11.1],
        ['Confirm', 50.0, 89.2, 12.2, 9.8],
        ['OK', 35.9, 85.9, 20.0, 12.0],
        ['Level Up Confirm', 50.0, 88.3, 12.6, 7.1],
    ],
}

DEFAULT_CONFIG = {
    'settings': DEFAULT_SETTINGS,
    'coordinates': DEFAULT_COORDINATES,
    'detection': {
        'Play Button': 'ocr',
        'SelectFo': 'ocr',
        'Relic Diamond': 'ocr',
    },
}
