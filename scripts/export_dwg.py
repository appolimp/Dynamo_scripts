# coding=utf-8
from base.wrapper import transaction, doc, DB, UI, uidoc
from base.exeption import ScriptError, ElemNotFound
import logging
import os.path

from System.Collections.Generic import List


VALID_VIEW_TYPE = [DB.ViewType.FloorPlan,
                   DB.ViewType.CeilingPlan,
                   DB.ViewType.Elevation,
                   DB.ViewType.ThreeD,
                   DB.ViewType.DrawingSheet,
                   DB.ViewType.DraftingView,
                   DB.ViewType.EngineeringPlan,
                   DB.ViewType.Section,
                   DB.ViewType.Detail,
                   ]

STANDARD_PREFIX = 'Inter your prefix or ~ for ignore'
DWG_OPTION_NAME = 'RC Layers Standard VBP'


@transaction
def main():
    return export_dwg(DWG_OPTION_NAME, STANDARD_PREFIX)


def export_dwg(dwg_option_name, standard_prefix):

    views_id = get_selected_views_id()
    dwg_option = get_dwg_option(dwg_option_name)

    path_with_name = get_path(standard_prefix)
    # path = r'C:\Users\appol\Desktop\Inter your prefix.dwg'
    folder, prefix = get_folder_and_prefix_by_path(path_with_name, standard_prefix)

    for view_id in views_id:
        name = prefix + get_name_view_by_id(view_id)
        col = List[DB.ElementId]([view_id])

        doc.Export(folder, prefix + name, col, dwg_option)
        delete_pcp_file(folder, name)

        logging.debug('View #{}. Export with name "{}"'.format(view_id, name))

    logging.info('Export {} files for folder: <{}>'.format(len(views_id), folder))


def delete_pcp_file(folder, name):
    path = os.path.join(folder, name + '.pcp')

    try:
        os.remove(path)
        logging.debug('Delete .pcp file by path <{}>'.format(path))
    except Exception:
        pass


def get_selected_views_id():
    pre_selected = uidoc.Selection.GetElementIds()
    selected_views_id = List[DB.ElementId]()

    for elem_id in pre_selected:
        elem = doc.GetElement(elem_id)
        if elem and isinstance(elem, DB.View) and elem.ViewType in VALID_VIEW_TYPE:
            selected_views_id.Add(elem_id)

    if selected_views_id:
        logging.debug('User select {} views'.format(len(selected_views_id)))
        return selected_views_id

    if doc.ActiveView.ViewType in VALID_VIEW_TYPE:
        logging.debug('Not found any valid selected view. So return ActiveView id')
        return List[DB.ElementId]([doc.ActiveView.Id])

    raise ElemNotFound('Valid selected view and ActiveView not found. ActiveView.ViewType is "{}"'.format(
        doc.ActiveView.ViewType))


def get_name_view_by_id(view_id):
    view = doc.GetElement(view_id)
    if view:
        return view.Name

    raise ElemNotFound('View #{}. Not found in document'.format(view_id))


def get_path(prefix):
    window = UI.FileSaveDialog("Файлы AutoCAD 2013 DWG (*.dwg)|*.dwg")
    window.InitialFileName = prefix
    window.Title = 'Choose folder and inter your prefix or ~ for ignore'
    window.Show()

    path = window.GetSelectedModelPath()

    if path:
        string_path = DB.ModelPathUtils.ConvertModelPathToUserVisiblePath(path)

        logging.debug('Get path from user: <{}>'.format(string_path))
        return string_path

    raise ElemNotFound('Cant get path from user')


def get_folder_and_prefix_by_path(path, standard_prefix):

    folder, name = os.path.split(path)
    prefix, ext = os.path.splitext(name)

    if prefix in [standard_prefix, '~']:
        prefix = ''
    else:
        logging.info('Get prefix: "{}"'.format(prefix))

    logging.info('Get folder <{}>'.format(folder))

    return folder, prefix


def get_dwg_option(option_name):
    setup_names = DB.BaseExportOptions.GetPredefinedSetupNames(doc)

    if option_name in setup_names:
        dwg_option = DB.DWGExportOptions.GetPredefinedOptions(doc, option_name)
        dwg_option.FileVersion = DB.ACADVersion.R2013

        logging.debug('Option name is valid: "{}"'.format(option_name))
        return dwg_option

    raise ElemNotFound('Setup name for export not found with name "{}"'.format(option_name))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%H:%M:%S')

    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
