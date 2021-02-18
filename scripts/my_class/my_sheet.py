from base.wrapper import doc, DB, Transaction
from base.exeption import ElemNotFound
from . import my_features, my_view, my_elem
import logging


@Transaction.ensure('Create sheet')
def create_sheet(title_block_symbol_id=DB.ElementId(-1)):
    """
    Create new sheet on current document by Symbol Id of TitleBlock

    :param title_block_symbol_id: TitleBlock.Symbol id
    :type title_block_symbol_id: DB.ElementId
    :return: New Sheet
    :rtype: DB.ViewSheet
    """

    sheet = DB.ViewSheet.Create(doc, title_block_symbol_id)

    logging.debug('Sheet #{}. Sheet was created with name: "{}"'.format(sheet.Id, sheet.Name))
    return sheet


def add_view_to_sheet(view, sheet, position=DB.XYZ(0, 0, 0)):
    view_port = DB.Viewport.Create(doc, sheet.Id, view.Id, position)

    logging.debug('View #{}. Viewport on sheet {} was created: #{}'.format(view.Id, sheet.Id, view_port.Id))
    return view_port


def create_sheet_by_views(views, name):
    sheet = create_sheet()
    set_name_for_sheet(sheet, name)

    viewports = []

    with Transaction('Add view port'):
        for view in views:
            viewport = add_view_to_sheet(view, sheet)
            viewports.append(viewport)

    _correct_positions(viewports)

    logging.info('Sheet "{}" with {} viewports was created'.format(name, len(viewports)))
    return sheet


@Transaction.ensure('Correct position on viewports')
def _correct_positions(viewports, start=DB.XYZ(0, 0, 0)):
    last_right = start
    for viewport in viewports:
        _correct_position_right(viewport, last_right, shift=0.1)
        last_right = viewport.GetBoxOutline().MaximumPoint


def _correct_position_right(viewport, last_right_up, shift=0.1):
    box = viewport.GetBoxOutline()
    center = viewport.GetBoxCenter()
    up, down = box.MaximumPoint, box.MinimumPoint

    shift_center = center + DB.XYZ(shift, 0, 0)
    new_center = shift_center - DB.XYZ(down.X - last_right_up.X,
                                       up.Y - last_right_up.Y, 0)
    viewport.SetBoxCenter(new_center)
    logging.debug('Set new position: {:.3f}, {:.3f}'.format(new_center.X, new_center.Y))
    return


@Transaction.ensure('Set sheet name')
def set_name_for_sheet(sheet, name):
    sheet.Name = name

    logging.debug('Set name for sheet: "{}"'.format(name))


def copy_sheet_with_param(sheet, params_for_copy=None):

    title_block = get_title_block_on_sheet(sheet)
    new_sheet = create_sheet(title_block.Symbol.Id)

    if type(params_for_copy) is dict and params_for_copy.get('title'):
        param_names = params_for_copy['title']
        new_title_block = get_title_block_on_sheet(new_sheet)
        my_elem.copy_params_by_name(title_block, new_title_block, param_names)

    if type(params_for_copy) is dict and params_for_copy.get('sheet'):
        param_names = params_for_copy['sheet']
        my_elem.copy_params_by_name(sheet, new_sheet, param_names)

    return new_sheet


def get_title_block_on_sheet(sheet):
    family_instances = my_features.get_depends_elems_by_class(sheet, DB.FamilyInstance)

    title_blocks = []
    for fam_inst in family_instances:
        if fam_inst.Category.Id == DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_TitleBlocks).Id:
            title_blocks.append(fam_inst)

    if len(title_blocks) > 1:
        logging.error('Sheet #{}. Have {} title blocks'.format(sheet.Id, len(title_blocks)))

    if title_blocks:
        logging.debug('Sheet #{}. Get tittle block #{}'.format(sheet.Id, title_blocks[0].Id))
        return title_blocks[0]

    raise ElemNotFound('Sheet #{}. Tittle block was not found'.format(sheet.Id))


def get_all_views(sheet):
    viewports = my_features.get_depends_elems_by_class(sheet, DB.Viewport)

    views_ids = [viewport.ViewId for viewport in viewports]
    views = my_features.get_elems_by_ids(views_ids)

    logging.debug('Sheet #{}. Get {} view on sheet'.format(sheet.Id, len(views)))

    return views


def get_viewports_position_by_view(view):
    viewports = my_features.get_depends_elems_by_class(view, DB.Viewport)

    for viewport in viewports:
        if viewport.SheetId != DB.ElementId.InvalidElementId:
            center_point = viewport.GetBoxCenter()

            logging.debug('View #{}. Get center point of Viewport on sheet: ({:.2f}, {:.2f}, {:.2f})'.format(
                view.Id, center_point.X, center_point.Y, center_point.Z))
            return center_point

    raise ElemNotFound('View #{}. Viewport with valid SheetId not found'.format(view.Id))


