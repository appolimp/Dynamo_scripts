# coding=utf-8
from my_class.base.wrapper import transaction, doc, DB
from my_class.base.exeption import ScriptError
import logging

from my_class import my_level
from my_class import my_view


def main():
    levels = my_level.Levels()
    copy_view(doc.ActiveView, levels)


def copy_view(view, levels):
    height = get_height_store_on_center_view(view, levels)
    new_view = my_view.duplicate_and_move_up(view, height)


def get_height_store_on_center_view(view, levels):
    center_view = my_view.get_center_point_of_view(view)

    height = levels.get_height_level_by_point(center_view)

    logging.debug('View #{}. Get height store {:.3f} m'.format(view.Id, height * 0.3048))
    return height


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error: ' + err.args[0])
