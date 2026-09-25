# Unseen dialogue navigator. Only adds callable helpers and an optional panel.
define config.console = True
init -5 python:
    import os as _unseen_os
    import sys as _unseen_sys
    _unseen_module_path = _unseen_os.path.join(config.basedir, "research_unseen")
    if _unseen_module_path not in _unseen_sys.path:
        _unseen_sys.path.insert(0, _unseen_module_path)
    import unseen_runtime as _unseen_research_runtime

    def unseen_research_jump(identifier):
        return _unseen_research_runtime.jump(identifier)

    def unseen_research_next(direction=1):
        return _unseen_research_runtime.next_fragment(direction)

    def unseen_research_text(key):
        return _unseen_research_runtime.navigator().text(key)

    def unseen_research_order():
        return _unseen_research_runtime.navigator().toggle_order()

    def unseen_research_order_text():
        nav = _unseen_research_runtime.navigator()
        return nav.text('events_order' if nav.queue_mode == 'events' else 'all_order')

    def unseen_research_status():
        return _unseen_research_runtime.navigator().panel_status()

screen unseen_research_controls():
    zorder 190
    frame:
        xalign 0.01
        yalign 0.12
        background "#101720dd"
        padding (12, 8)
        vbox:
            spacing 5
            text unseen_research_text("title") size 17 color "#c2dbf5"
            text unseen_research_status() size 13 color "#c2dbf5" xmaximum 650 substitute False
            textbutton unseen_research_order_text() action Function(unseen_research_order) text_size 14
            hbox:
                spacing 12
                textbutton unseen_research_text("previous") action Function(unseen_research_next, -1) text_size 16
                textbutton unseen_research_text("next") action Function(unseen_research_next) text_size 16
                textbutton unseen_research_text("hide") action Hide("unseen_research_controls") text_size 16
