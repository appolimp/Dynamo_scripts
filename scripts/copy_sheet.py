# coding=utf-8
from my_class.base.wrapper import transaction, doc, DB
from my_class.base.exeption import ScriptError
import logging

from my_class import my_level, my_view, my_sheet, my_features

# Get config
import ConfigParser as configparser
import os

COMPANY = 'EGP'

this_folder = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(this_folder, 'data')
init_file = os.path.join(data_folder, 'copy_sheet.ini')
CONFIG = configparser.ConfigParser()
CONFIG.read(init_file)



def main():
    view = doc.ActiveView
    sheet_param_for_copy = get_sheet_param_for_copy()
    sheet = full_copy_up_sheet(view, sheet_param_for_copy)
    return


def full_copy_up_sheet(old_sheet, sheet_param_for_copy):
    new_sheet = my_sheet.copy_sheet_with_param(old_sheet, sheet_param_for_copy)
    levels = my_level.Levels()

    views = my_sheet.get_all_views(old_sheet)
    for view in views:
        if view.ViewType in [DB.ViewType.Section, DB.ViewType.Elevation]:
            new_view = copy_view(view, levels)

            old_position = my_sheet.get_viewports_position_by_view(view)
            new_viewport = my_sheet.add_view_to_sheet(new_view, new_sheet, old_position)

    logging.info('Sheet #{}. New sheet was copied from sheet #{}. With all views and annotations'.format(
        new_sheet.Id, old_sheet.Id))

    return new_sheet


def get_sheet_param_for_copy():
    config_param_sheet = CONFIG.get(COMPANY, 'Sheet_param_for_copy').decode('utf-8')
    param_sheet = config_param_sheet.split(';')

    config_param_title = CONFIG.get(COMPANY, 'Title_param_for_copy').decode('utf-8')
    param_title = config_param_title.split(';')

    logging.info('Get param for copy sheet from config: {} to sheet, {} to title'.format(
        len(param_sheet), len(param_title)))
    return {'sheet': param_sheet, 'title': param_title}


def copy_view(view, levels):
    height = get_height_store_on_center_view(view, levels)
    new_view = my_view.duplicate_and_move_up(view, height)

    return new_view


def get_height_store_on_center_view(view, levels):
    center_view = my_view.get_center_point_of_view(view)

    height = levels.get_height_level_by_point(center_view)

    logging.info('View #{}. Get height store {:.3f} m'.format(view.Id, height * 0.3048))
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
