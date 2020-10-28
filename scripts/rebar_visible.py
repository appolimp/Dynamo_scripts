# coding=utf-8
from base.wrapper import transaction, doc
from base.exeption import ScriptError
from rebar import unobscured_all_selected_rebars_on_view, unobscured_all_rebars_on_view
import logging


@transaction
def main():
    ONLY_SELECTED = IN[0]
    if ONLY_SELECTED:
        unobscured_all_selected_rebars_on_view(doc.ActiveView, True, True)
    else:
        unobscured_all_rebars_on_view(doc.ActiveView, True, True)


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')