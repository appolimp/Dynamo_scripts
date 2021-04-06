# -*- coding: utf-8 -*-
"""
Page:
Title: Назначить номер помещения элементам отделки
"""

from wrapper import transaction, DB, UI, errors
import System
import logging

from System import Enum
from System.Collections.Generic import List
from Autodesk.Revit.Exceptions import InvalidOperationException

uiapp = __uiapp__
uidoc = uiapp.ActiveUIDocument
doc = uidoc.Document
app = doc.Application
inputs = __inputs__

SELECTION_MODE_KEY = inputs['selection'].Content
SELECT_ALL = 'All'
SELECT_SELECTED = 'Selected'
SELECT_BY_VIEW = 'Visible'
SELECT_BY_GROUP = 'ofGroup'

SELECTION_MODES = {
    'Все помещения': SELECT_ALL,
    'Выбранные помещения': SELECT_SELECTED,
    'Видимые на виде помещения': SELECT_BY_VIEW,
    'Выбранной группы помещения': SELECT_BY_GROUP
}
SELECTION_MODE = SELECTION_MODES.get(SELECTION_MODE_KEY, SELECT_SELECTED)

PVP = inputs['pvp']
PVP_PAR_NAME = inputs['pvpParName']
PVP_PAR_VAL = inputs['pvpParVal']

OPTIONS = DB.Options()

PAR_ROOM_NUMBER = inputs['parRoomNumber']
PAR_NUMBER = inputs['parNumber']


@transaction(doc)
def main():
    link_with_room = get_link_by_name('Rooms')  # TODO
    link_transform = link_with_room.GetTotalTransform()  # TODO
    rooms = collect_elements(doc_=link_with_room.GetLinkDocument())  # TODO
    for room in rooms:
        if room.Area == 0:
            continue

        room_number = room.LookupParameter(PAR_ROOM_NUMBER).AsString()
        logging.debug('Get room_number "{}"'.format(room_number))
        if room_number:
            room_box = room.get_BoundingBox(None)
            room_box.Transform = room_box.Transform.Multiply(link_transform)

            room_solid = get_solids(room)[0]
            transformed_room_solid = DB.SolidUtils.CreateTransformed(room_solid, link_transform)  # TODO
            collector = collect_by_bbox(room_box, room_id=room.Id)
            # Если возвращает пустой коллектор. можно попробовать отправлять BoundingBox от transformed_room_solid

            collector.WherePasses(DB.ElementIntersectsSolidFilter(transformed_room_solid))
            for el in collector:
                set_parameter_by_name(el, PAR_NUMBER, room_number)
                logging.info('Элементу #{} присвоен номер помещения: "{}"'.format(el.Id, room_number))
            logging.info('End Script')
        else:
            logging.warning('У помещения "{}" отсутствует номер для параметра "{}"'.format(room.Id, PAR_ROOM_NUMBER))

    logging.debug('End')


def get_link_by_name(link_name):  # TODO
    collector = DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance)
    for link in collector:
        if link_name in link.Name:
            logging.debug('Get link by name "{}"'.format(link.Name))
            return link

    raise errors.ScriptError('Link with name "{}" not found'.format(link_name))


def get_elements_by_not_part(collector):
    elements = []
    for el in collector:
        do = el.DesignOption
        if do: continue
        elements.append(el)
    return elements


def get_parameter_id_by_name():
    col = DB.FilteredElementCollector(doc).OfClass(DB.ParameterElement).ToElements()
    parameter = [p for p in col if p.Name == PVP_PAR_NAME][0]
    return parameter.Id


def collect_elements(doc_=doc):
    logging.debug('Start collect')
    cat_list = List[DB.BuiltInCategory]([DB.BuiltInCategory.OST_Rooms])

    cat_filter = DB.ElementMulticategoryFilter(cat_list)

    if SELECTION_MODE == SELECT_SELECTED:
        logging.debug('SELECT_SELECTED')
        col = DB.FilteredElementCollector(doc_, get_selected_ids())

    elif SELECTION_MODE == SELECT_BY_VIEW:
        logging.debug('SELECT_BY_VIEW')
        col = DB.FilteredElementCollector(doc_, doc_.ActiveView.Id)

    elif SELECTION_MODE == SELECT_BY_GROUP:
        logging.debug('SELECT_BY_GROUP')
        members = get_selected_by_groups()
        col = DB.FilteredElementCollector(doc_, List[DB.ElementId](members))

    else:
        logging.debug('All')
        col = DB.FilteredElementCollector(doc_)
    logging.debug('return collector')
    col.WherePasses(cat_filter).WhereElementIsNotElementType()
    return col


def get_selected_ids():
    selected_ids = uidoc.Selection.GetElementIds()
    if not selected_ids:
        raise errors.ScriptError('Ничего не выбрано.')
    return selected_ids


def get_selected_by_groups():
    groups = DB.FilteredElementCollector(doc, get_selected_ids()).OfCategory(DB.BuiltInCategory.OST_IOSModelGroups)
    members = []
    for group in groups:
        member_ids = group.GetMemberIds()
        for member_id in member_ids:
            members.append(member_id)
    return members


def get_category(cat_name):
    categories = doc.Settings.Categories
    categories_dict = {cat.Name: cat for cat in categories}
    category = categories_dict[cat_name]
    builtin_category = System.Enum.ToObject(DB.BuiltInCategory, category.Id.IntegerValue)
    return builtin_category


def create_cat_filter():
    cat_list = List[DB.BuiltInCategory]([DB.BuiltInCategory.OST_Roofs,
                                         DB.BuiltInCategory.OST_Floors,
                                         DB.BuiltInCategory.OST_Walls])

    cat_filter = DB.ElementMulticategoryFilter(cat_list)
    return cat_filter


def collect_by_bbox(bbox, offset=0.3, collector=None, room_id=None):
    outline = DB.Outline(
        DB.XYZ(bbox.Min.X - offset, bbox.Min.Y - offset, bbox.Min.Z - offset),
        DB.XYZ(bbox.Max.X + offset, bbox.Max.Y + offset, bbox.Max.Z + offset))
    bbox_filter = DB.BoundingBoxIntersectsFilter(outline)
    ids_to_exclude = List[DB.ElementId]([room_id])

    cat_filter = create_cat_filter()

    if not collector:
        collector = DB.FilteredElementCollector(doc).Excluding(ids_to_exclude).WherePasses(bbox_filter)
        collector.WherePasses(cat_filter)
    else:
        collector.Excluding(ids_to_exclude).WherePasses(bbox_filter)
        collector.WherePasses(cat_filter)

    if PVP:
        fam_par_id = get_parameter_id_by_name()
        pvp = DB.ParameterValueProvider(fam_par_id)
        filter_rule = DB.FilterStringRule(pvp, DB.FilterStringContains(), PVP_PAR_VAL, True)
        element_par_filter = DB.ElementParameterFilter(filter_rule)
        collector.WherePasses(element_par_filter)
    else:
        pass

    collector.WherePasses(cat_filter).WhereElementIsNotElementType()
    return collector


def get_solids(element, options=OPTIONS):
    geo = element.get_Geometry(options)
    solids = []
    for g in geo:
        # GeometryInstance
        if type(g) == DB.GeometryInstance:
            transform = g.Transform
            symbol_geo = g.SymbolGeometry
            symbol_mat = symbol_geo.MaterialElement
            for sub_g in symbol_geo.GetTransformed(g.Transform):
                if type(sub_g) == DB.Solid and sub_g.Volume > 0:
                    solids.append(sub_g)
        if type(g) == DB.Solid and g.Volume > 0:
            solids.append(g)
    return solids


def collect_by_intersect(element):
    element_solids = get_solids(element)
    if not element_solids:
        return
    element_solid = get_solids(element)[0]
    collector = collect_by_bbox(element)
    collector.WherePasses(DB.ElementIntersectsSolidFilter(element_solid))
    elements_bbox = get_elements_by_not_part(collector)
    return elements_bbox


def get_point_by_side_face(element):
    layer_type = DB.ShellLayerType.Interior
    references = DB.HostObjectUtils.GetSideFaces(element, layer_type)

    for ref in references:
        face = element.GetGeometryObjectFromReference(ref)
        if face:
            origin = face.FaceNormal
            # return origin
            angle_radians = origin.AngleTo(DB.XYZ.BasisZ)
            return angle_radians
            # angle_degrees = angle_radians * 180 / math.pi


def set_parameter_by_name(element, par_name, par_val):
    parameter = element.LookupParameter(par_name)
    try:
        parameter.Set(par_val)
    except InvalidOperationException:
        logging.warning('#{}: Parameter только для чтения {}'.format(element.Id, par_name))
    except AttributeError:
        logging.warning('#{}: Параметр не существует {}'.format(element.Id, par_name))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')
    try:
        main()
    except errors.ScriptError as e:
        logging.error(e)
    except:
        logging.exception('Critical Error')
