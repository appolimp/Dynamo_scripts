# coding=utf-8
import time

start = time.time()

from base.wrapper import transaction, UnwrapElement, app, Ex, uidoc, TransactionManager, clr
from base.selection import get_selected, get_selected_by_cat
from base.exeption import ScriptError, ElemNotFound
from System.Collections.Generic import List
import logging
import os.path
import sys

sys.path.append(IN[5])
from color_param import find_filter, set_rule
from Autodesk.Revit.UI.Selection import ISelectionFilter, PickBoxStyle
from rpw import revit, db, ui, doc, logger, DB, UI
from collections import namedtuple
from base.selection import get_selected_by_cat, get_selected

from create_callout import GeometryInRevit, MyView
from abc import ABCMeta, abstractmethod, abstractproperty


class MySelectionFilter(ISelectionFilter):
    def __init__(self, cat, *args):
        ISelectionFilter.__init__(self, *args)
        self.cat = cat

    def AllowElement(self, elem):
        cat_id = DB.Category.GetCategory(doc, self.cat).Id
        if elem.Category.Id == cat_id:
            return True
        return False

    def AllowReference(self, reference, position):
        return False


class MyRefFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return True

    def AllowReference(self, reference, position):
        return True


class MyContext(DB.IExportContext):
    def __init__(self, doc_):
        self.doc = doc_

    def Start(self):
        return True

    def Finish(self):
        pass


class Creator:
    def __init__(self):
        self._app = app.Create
        self._doc = doc

    @staticmethod
    def new_sketch_plane_pass_line(line):
        first_point = line.GetEndPoint(0)
        end_point = line.GetEndPoint(1)
        direct = end_point - first_point

        if round(direct.Z, 3) == 0:
            norm = DB.XYZ.BasisZ
        elif round(direct.X, 3) == 0:
            norm = DB.XYZ.BasisX
        else:
            norm = DB.XYZ.BasisY

        plane = DB.Plane.CreateByNormalAndOrigin(norm, first_point)
        sketch = DB.SketchPlane.Create(doc, plane)

        return sketch

    def create_model_line(self, first_point, end_point):
        assert not first_point.IsAlmostEqualTo(end_point)

        line = DB.Line.CreateBound(first_point, end_point)
        sketch = self.new_sketch_plane_pass_line(line)

        return doc.Create.NewModelCurve(line, sketch)

    def draw_polygons(self, loops):
        polygons = []
        for loop in loops:
            polygon = []
            sec_loop = loop[1:] + [loop[0]]
            for first, end in zip(loop, sec_loop):
                line = self.create_model_line(first, end)
                polygon.append(line)
            polygons.append(polygon)
        return polygons


class MySectionCreatorBase:
    __metaclass__ = ABCMeta
    OFFSET_HEIGHT = 2
    OFFSET_WIDTH = 2
    OFFSET_DEPTH = 2
    OFFSET_CUT_LINE = 2

    ViewFamilyType = None

    def __init__(self, element):
        self.element = element
        self.calc_geom_param()

        self.origin = element.origin
        self.height_up = element.height_up
        self.height_down = element.height_down

    @abstractmethod
    def calc_geom_param(self):
        self.width = self.element._length
        self.thicknes = self.element._width

    def create_section(self, direction, section_family=None):
        if section_family is None:
            section_family = self._get_section_view_family_type()

        box = self.create_bounding_box(direction)
        section = DB.ViewSection.CreateSection(doc, section_family.Id, box)
        return section

    def create_bounding_box(self, direction):
        t = DB.Transform.Identity
        t.Origin = self.origin

        t.BasisX = direction
        t.BasisY = DB.XYZ.BasisZ
        t.BasisZ = t.BasisX.CrossProduct(t.BasisY)

        box = DB.BoundingBoxXYZ()
        box.Transform = t

        box.Max, box.Min = self._calc_points_to_box()
        return box

    def _calc_points_to_box(self):
        down = DB.XYZ(
            -self.width / 2 - self.OFFSET_WIDTH,  # length left
            self.height_down - self.OFFSET_HEIGHT,  # height down
            -self.thicknes / 2 - self.OFFSET_CUT_LINE)  # offset of cut line

        up = DB.XYZ(
            self.width / 2 + self.OFFSET_WIDTH,  # length right
            self.height_up + self.OFFSET_HEIGHT,  # height up
            self.thicknes / 2 + self.OFFSET_DEPTH)  # offset of far clip

        return up, down

    @classmethod
    def _get_section_view_family_type(cls):
        if cls.ViewFamilyType is None:
            logging.debug('Calc view family')
            collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType)
            for elem in collector:
                if elem.ViewFamily == DB.ViewFamily.Section:
                    MySectionCreatorBase.ViewFamilyType = elem

        return MySectionCreatorBase.ViewFamilyType


class MyAcrossSectionCreator(MySectionCreatorBase):

    def calc_geom_param(self):
        self.width = self.element._width
        self.thicknes = 0


class MyAlongSectionCreator(MySectionCreatorBase):

    def calc_geom_param(self):
        self.width = self.element._length
        self.thicknes = self.element._width


class MySectionMixIn(object):
    def __init__(self, element):
        super(MySectionMixIn).__init__(element)
        self._calc_up_down_height()

    def _calc_origin_and_orientation(self):
        first, second = self.element.Location.Curve.GetEndPoint(0), self.element.Location.Curve.GetEndPoint(1)
        self.origin = (first + second) / 2.0
        self.orientation = self.element.Location.Curve.Direction

    def _calc_up_down_height(self):

        # FIXME It is very bad, need think
        # Почему то на активном виде некорректные точки в BoundingBox
        solid = GeometryInRevit.get_geom_by_elem(self.element)
        box = solid.GetBoundingBox()

        self.height_up = box.Max.Z
        self.height_down = box.Min.Z
        self.origin = DB.XYZ(self.origin.X, self.origin.Y, solid.ComputeCentroid().Z)

    def create_along_section(self, flip=False):
        line = (1 if flip else -1) * self.orientation
        section = MyAlongSectionCreator(self).create_section(line)
        return section

    def create_across_section(self, flip=False):
        line = (1 if flip else -1) * DB.XYZ.BasisZ.CrossProduct(self.orientation)
        section = MyAlongSectionCreator(self).create_section(line)
        return section

    @abstractproperty
    def _width(self):
        """
        Return width of wall via it parameter

        :return: Width
        :rtype: float
        """
        return self.element.Width

    @abstractproperty
    def _length(self):
        return self.element.Location.Curve.Length


@transaction
def main():
    return create_section()


def create_section():
    wall = UnwrapElement(IN[4])
    sections = MySectionMixIn(wall)
    first = sections.create_along_section()
    second = sections.create_across_section()
    third = sections.create_along_section(flip=True)
    fourth = sections.create_across_section(flip=True)

    return first, second, third, fourth


def user_selection_by_cat(cat):
    elem_filter = MySelectionFilter(cat)
    elems = uidoc.Selection.PickElementsByRectangle(elem_filter, 'select elements {}'.format(cat))

    logging.info('User select {}'.format(len(elems)))
    return elems


def get_user_point():
    point = uidoc.Selection.PickPoint('Select point')
    return point


def get_lines(style_name):
    lines = DB.FilteredElementCollector(doc, doc.ActiveView.Id).OfCategory(DB.BuiltInCategory.OST_Lines)
    res = []
    for line in lines:
        if line.LineStyle.Name == style_name:
            res.append(line)
    return res


def glob_param():
    elem_id = uidoc.Selection.GetElementIds()[0]
    elem = doc.GetElement(elem_id)
    params = elem.LookupParameter('Номинал MCB')
    print params.AssociateWithGlobalParameter()


def user_select():
    elements = uidoc.Selection.PickElementsByRectangle('select ')
    another = uidoc.Selection.PickBox(UI.Selection.PickBoxStyle.Crossing)


def filtered_autodesk():
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View3D)
    views = collector.Cast()
    for room in views:
        print room


def split_lines():
    lines_revit = db.Collector(view=doc.ActiveView, of_class=DB.CurveElement).get_elements(wrapped=False)
    box = []
    for line in lines_revit:
        if line.LineStyle.Name == '<Линии>':
            split_line = line.GeometryCurve
        else:
            box.append(line.GeometryCurve)

    splinted_line = []
    just_box = []
    splinted_point = []

    for line in box:
        intersect = clr.StrongBox[DB.IntersectionResultArray]()
        is_intersect = line.Intersect(split_line, intersect)

        if is_intersect == DB.SetComparisonResult.Overlap:
            point = intersect.Value[0].XYZPoint
            splinted_point.append(point)
            print 1
        elif is_intersect == DB.SetComparisonResult.Disjoint:
            splinted_point.append(line)
            just_box.append(line)
            print 2
        else:
            print is_intersect


def copy_sheet():
    # Get Sheet and TitleBlock and Legend
    sheet = get_sheet()
    title_block = get_elem_by_cat_and_family_name_on_view(category=DB.BuiltInCategory.OST_TitleBlocks,
                                                          block_name='РЕН КОНС Листы v2', view=sheet)
    legend = get_legend_on_view(sheet)

    # Get next number for sheet
    next_number = get_next_number(sheet)

    # Create new sheet and set number
    new_sheet = create_sheet(title_block)
    new_title_block = get_elem_by_cat_and_family_name_on_view(category=DB.BuiltInCategory.OST_TitleBlocks,
                                                              block_name='РЕН КОНС Листы v2', view=new_sheet)
    set_value_param(param=new_sheet.get_Parameter(DB.BuiltInParameter.SHEET_NUMBER),
                    value=next_number)
    set_value_param(param=new_sheet.LookupParameter('Нестандартный номер листа'),
                    value=next_number.rpartition('-')[-1])

    # TODO add Подпись2 as current user in pyRevit and Комаристов
    # Copy parameters by TitleBlock and Sheet
    fill_param_on_elem_from_old_elem_by_name(new=new_title_block,
                                             old=title_block,
                                             names=('Подпись3', 'Подпись4', 'Подпись5'))
    fill_param_on_elem_from_old_elem_by_name(new=new_sheet,
                                             old=sheet,
                                             names=('Наим. объекта', 'Марка', 'Доп. шифр'))

    # Create legend
    # FIXME 20201016 RevitAPI cant move title of viewport, one solution in revit 2020. just copy legend
    new_legend = DB.Viewport.Create(doc, new_sheet.Id, legend.ViewId, legend.GetBoxCenter())
    new_legend.ChangeTypeId(legend.GetTypeId())
    # legend = get_legend_on_view(sheet)  # For Revit 2020: copy legend to new sheet

    # Copy annotation
    stamp = get_elem_by_cat_and_family_name_on_view(category=DB.BuiltInCategory.OST_TitleBlocks,
                                                    block_name='S_Annotations_AddStamp',
                                                    view=sheet)
    keyplan = get_elem_by_cat_and_family_name_on_view(category=DB.BuiltInCategory.OST_GenericAnnotation,
                                                      block_name='S_Annotations_Generic_Keyplan.Wall.small',
                                                      view=sheet)
    text_notes = get_all_text_note_on_view(view=sheet)

    copy_elements = [stamp] + [keyplan] + text_notes
    copy_element_ids = List[DB.ElementId]([elem.Id for elem in copy_elements])

    DB.ElementTransformUtils.CopyElements(sheet,
                                          copy_element_ids,
                                          new_sheet,
                                          None, None)


def get_sheet():
    """
    Get selected sheet or active view if sheet

    :return: Sheet
    :rtype: DB.ViewSheet
    """

    sheets = get_selected_by_cat(DB.BuiltInCategory.OST_Sheets, as_list=True)
    if sheets:
        if len(sheets) > 1:
            raise ScriptError("Please select only one sheet")  # FIXME
        return sheets[0]
    else:
        sheet = doc.ActiveView
        if sheet.ViewType != DB.ViewType.DrawingSheet:
            raise ScriptError("ActiveView is not sheet")  # FIXME
        return sheet


def get_elem_by_cat_and_family_name_on_view(category, block_name, view):
    """
    Get elem by category and family name on view

    :param category: DB.BuiltInCategory
    :type category: DB.BuiltInCategory
    :param block_name: Family name
    :type block_name: str
    :param view: Sheet
    :type view: DB.ViewSheet
    :return: instanse of TitleBlock
    :rtype: DB.FamilyInstance
    """
    collector = DB.FilteredElementCollector(doc, view.Id).OfCategory(category).ToElements()
    for block in collector:
        if block.Symbol.Family.Name == block_name:
            return block
    raise ElemNotFound('{} on sheet not found'.format(category))


def get_all_text_note_on_view(view):
    """
    Get all TextNote on view

    :param view: Sheet
    :type view: DB.ViewSheet
    :return: List TextNote
    :rtype: list[DB.TextNote]
    """

    collector = DB.FilteredElementCollector(doc, view.Id).OfCategory(DB.BuiltInCategory.OST_TextNotes).ToElements()
    return list(collector)


def get_legend_on_view(view):
    """
    Get legend view on view. Need for revit2020, which can copy legend

    :param view: View
    :type view: DB.View
    :return: View of Legend
    :rtype: DB.View
    """

    collector = DB.FilteredElementCollector(doc, view.Id).OfCategory(DB.BuiltInCategory.OST_Viewports).ToElements()
    for view_port in collector:
        view = doc.GetElement(view_port.ViewId)
        if view.ViewType == DB.ViewType.Legend:
            return view_port

    raise ElemNotFound('Legend on sheet not found')


@transaction(msg='Copy selected sheet')
def create_sheet(title_block):
    """
    Create new sheet on current document by TitleBlock

    :param title_block: instanse of TitleBlock
    :type title_block: DB.FamilyInstance
    :return: New Sheet
    :rtype: DB.ViewSheet
    """
    return DB.ViewSheet.Create(doc, title_block.Symbol.Id)


def fill_param_on_elem_from_old_elem_by_name(new, old, names):
    """
    Скопировать значения параметра из одного элемента в другой по имени

    :param new: Element which will fill
    :type new: DB.Element
    :param old: Element for parameters
    :type old: DB.Element
    :param names: Name parameters
    :type names: tuple[str]
    """

    for name in names:
        param = new.LookupParameter(name)
        if param.StorageType == DB.StorageType.ElementId:
            value = old.LookupParameter(name).AsElementId()
            if value:
                set_value_param(param, value)
        elif param.StorageType == DB.StorageType.String:
            value = old.LookupParameter(name).AsString()
            if value:
                set_value_param(param, value)
        elif param.StorageType == DB.StorageType.Integer:
            value = old.LookupParameter(name).AsInteger()
            if value:
                set_value_param(param, value)
        else:
            print param.StorageType


@transaction(msg='Set parameter value')
def set_value_param(param, value):
    """
    Установить параметру данное значение

    :param param: Параметр
    :type param: DB.Parameter
    :param value: Значение
    :type value: int or float or str, DB.ElementId
    """

    param.Set(value)


def get_next_number(sheet):
    """
    Получить следующий номер листа

    :param sheet: Sheet
    :type sheet: DB.SheetView
    :return: <Марка>-<Номер листа>
    :rtype: str
    """

    num_value = sheet.get_Parameter(DB.BuiltInParameter.SHEET_NUMBER).AsString()
    mark, _, number = num_value.rpartition('-')
    max_number = int(number)

    collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet).WhereElementIsNotElementType().ToElements()
    for temp_sheet in collector:
        temp_value = temp_sheet.get_Parameter(DB.BuiltInParameter.SHEET_NUMBER).AsString()
        temp_mark, _, temp_number = temp_value.rpartition('-')
        if temp_mark == mark:
            if temp_number.isdigit() and int(temp_number) > max_number:
                max_number = int(temp_number)

    return mark + '-' + str(max_number + 1).rjust(len(number), '0')


@transaction(msg='Copy family instanse to view')
def copy_family_inst_to_view(inst, view):
    """
    Copy family instanse to view in the same location

    :param inst: Family instanse
    :type inst: DB.FamilyInstance
    :param view: View
    :type view: DB.View
    """

    new_inst = doc.Create.NewFamilyInstance(inst.Location.Point,
                                            inst.Symbol,
                                            view)
    return new_inst


def default_type():
    """
    Изменить тип стены по умолчанию на выбранную
    """

    wall = get_selected(as_list=True)[0]
    def_elem_type_id = doc.GetDefaultElementTypeId(DB.ElementTypeGroup.WallType)
    doc.SetDefaultElementTypeId(DB.ElementTypeGroup.WallType, wall.WallType.Id)


def draw_bounds_floor():
    del_all_on_active_view_by_cat(DB.BuiltInCategory.OST_Lines)

    # Получение геометрии
    floor = UnwrapElement(IN[4])
    opt = app.Create.NewGeometryOptions()
    geometries = floor.get_Geometry(opt)

    for solid in geometries:
        bounds = get_boundary(solid)

    # Вычисление площади
    area = []
    for f_bounds in flatten_polygons(bounds):
        area.append(get_signed_polygon_area(f_bounds))

    # Рисование линий модели
    creator = Creator()
    polygons = creator.draw_polygons(bounds)

    # Поиск самой большой границы
    res_polygons = zip(polygons, area)
    bound_polygon = max(res_polygons, key=lambda x: abs(x[1]))[0]

    # Поиск стиля линии
    collector = DB.FilteredElementCollector(doc).OfClass(
        DB.GraphicsStyle).WhereElementIsNotElementType().ToElements()
    for style in collector:
        if style.Name == '*Magenta':
            new_style_line = style
            break
    else:
        raise ElemNotFound

    # Изменение стиля линии
    for line in bound_polygon:
        line.LineStyle = new_style_line

    return bound_polygon


def del_all_on_active_view_by_cat(cat):
    """
    Удалить все элементы данной категории на активном виде

    :param cat: Категория
    :type cat: DB.BuiltInCategory
    """

    collector = DB.FilteredElementCollector(doc, doc.ActiveView.Id).OfCategory(
        cat).WhereElementIsNotElementType().ToElementIds()

    doc.Delete(collector)


def get_boundary(solid):
    # FIXME ошибка при большой боковой площади
    lowest_face = sorted(solid.Faces, key=lambda x: x.Area)[-1]
    normal = lowest_face.ComputeNormal(DB.UV(0.5, 0.5))

    loops = lowest_face.EdgeLoops
    polygons = []
    for loop in loops:
        polygon = []

        for edge in loop:
            points = list(edge.Tessellate())

            if polygon:
                assert not polygon[-1].IsAlmostEqualTo(points[0])

            polygon.extend(points[:-1])

        polygons.append(offset_polygon(polygon, offset=normal * 0.1))
    DB.FilteredElementCollector(doc)
    return polygons


def offset_polygon(polygon, offset=DB.XYZ(0, 0, 0.1)):
    """
    Смещает полигон на вектор

    :param polygon: Список точек
    :type polygon: list[DB.XYZ]
    :param offset: Вектор
    :type offset: DB.XYZ
    :return: Смещенный список точек
    :rtype: list[DB.XYZ]
    """

    return [point + offset for point in polygon]


def some_act_with_polygons():
    polygon_1 = [DB.XYZ(2, 9, 0),
                 DB.XYZ(6, 14, 0),
                 DB.XYZ(9, 9, 0),
                 DB.XYZ(2, 2, 0),
                 ]

    polygon_2 = [DB.XYZ(1, 9, 0),
                 DB.XYZ(6, 5, 0),
                 DB.XYZ(9, 9, 0),
                 DB.XYZ(2, 2, 0),
                 ]

    polygons = [polygon_1, polygon_2]

    f_polygons = flatten_polygons(polygons)
    for f_polygon in f_polygons:
        print get_signed_polygon_area(f_polygon)


def get_signed_polygon_area(points):
    """
    Get area 2d polygon

    :param points: list[DB.UV]
    :type points: list[DB.UV]
    :return: Area
    :rtype: float
    """

    area = 0
    j = points[len(points) - 1]

    for i in points:
        area += (j.U + i.U) * (j.V - i.V)
        j = i

    return area / 2


def flatten_point(point):
    """
    Спроецировать точку на горизонтальную плоскость как вектор в двумерном пространстве

    :param point: Point
    :type point: DB.XYZ
    :return: new DB.UV
    :rtype: DB.UV
    """

    return DB.UV(point.X, point.Y)


def flatten_polygon(polygon):
    """
    Спроецировать список точек на горизонтальную плоскость

    :param polygon: Лист точек
    :type polygon: list[DB.XYZ]
    :return: Лист плоских точек
    :rtype: list[DB.UV]
    """

    return List[DB.UV](flatten_point(point) for point in polygon)


def flatten_polygons(polygons):
    """
    Спроецировать список полигонов на горизонтальную плоскость

    :param polygons: Список полигонов
    :type polygons: list[list[DB.XYZ]]
    :return: Лист плоских точек
    :rtype: list[list[DB.UV]]
    """

    return List[List[DB.UV]](flatten_polygon(polygon) for polygon in polygons)


def exporter():
    """

    url: https://thebuildingcoder.typepad.com/blog/2013/07/graphics-pipeline-custom-exporter.html
    """

    context = MyContext(doc)
    export = DB.CustomExporter(doc, context)
    export.Export(doc.ActiveView)

    return


def task_dialog():
    window = UI.TaskDialog('Title')
    window.TitleAutoPrefix = False
    window.MainIcon = UI.TaskDialogIcon.TaskDialogIconShield
    window.MainInstruction = 'Main instruction'
    window.MainContent = 'Main content'

    window.EnableMarqueeProgressBar = True

    window.CommonButtons = UI.TaskDialogCommonButtons.Ok | UI.TaskDialogCommonButtons.Cancel
    window.DefaultButton = UI.TaskDialogResult.Ok

    window.AddCommandLink(UI.TaskDialogCommandLinkId.CommandLink1, "First")
    window.AddCommandLink(UI.TaskDialogCommandLinkId.CommandLink2, "Second", "support content")

    # window.EnableDoNotShowAgain("My_window1", True, "Do not show again")
    # window.VerificationText = 'Verification text'
    # window.ExtraCheckBoxText = 'Extra check box text'

    window.ExpandedContent = "Expanded text"
    window.FooterText = 'Footer text'

    t_result = window.Show()

    # print window.WasVerificationChecked()
    print t_result


@transaction
def edit_view_crop():
    """
    x_1, y_1 = l_d.X, l_d.Y
    x_2, y_2 = r_u.X, r_u.Y

    l_u = DB.XYZ(x_1, y_2, 0.0)
    r_d = DB.XYZ(x_2, y_1, 0.0)

    curves = List[DB.Curve]()
    curves.Add(DB.Line.CreateUnbound(l_d, l_u))
    curves.Add(DB.Line.CreateUnbound(l_u, r_u))
    curves.Add(DB.Line.CreateUnbound(r_u, r_d))
    curves.Add(DB.Line.CreateUnbound(r_d, l_d))
    """
    """
    curves = List[DB.Curve]([DB.Line.CreateBound(l_d, r_u)])

    curve_loop = DB.CurveLoop.Create(curves)

    active_view = doc.ActiveView
    crop_shape = active_view.GetCropRegionShapeManager()
    crop_shape.SetCropShape(curve_loop)
    """

    box = DB.BoundingBoxXYZ()
    user_select_rect = box_selection()
    box.Min, box.Max = convert_two_point(*user_select_rect)

    doc.ActiveView.CropBox = box
    return box


def box_selection():
    """
        Get two points by user rectangle selection

        :returns (DB.XYZ, DB.XYZ)
        """
    data = uidoc.Selection.PickBox(PickBoxStyle.Enclosing, 'select two point')
    return data.Min, data.Max


def transform_point_for_section(first, second, side, flip_direction):
    """
    Convert point for section
    Using origin shaft and view direction

    :param first: DB.XYZ
    :param second: DB.XYZ
    :param side: str
    :param flip_direction: bool

    :returns (DB.XYZ, DB.XYZ)
    """
    origin = doc.ActiveView.Origin

    point_x = [getattr(elem, side) for elem in (first, second)]
    point_z = [getattr(elem, 'Z') for elem in (first, second)]

    point_left = DB.XYZ(min(point_x) - getattr(origin, side), min(point_z) - origin.Z, 0)
    point_right = DB.XYZ(max(point_x) - getattr(origin, side), max(point_z) - origin.Z, 0)

    if flip_direction:  # Need for flip section
        left_x, right_x = point_left.X, point_right.X
        point_left = DB.XYZ(-right_x, point_left.Y, 0)
        point_right = DB.XYZ(-left_x, point_right.Y, 0)

    return point_left, point_right


def convert_two_point(first, second):
    """
        Convert point for BoundingBoxXYZ
        return left_down and right_up points

        :param first: DB.XYZ
        :param second: DB.XYZ

        :returns (DB.XYZ, DB.XYZ)
        """
    direction = doc.ActiveView.ViewDirection

    if round(direction.X - direction.Y, 5) == 0:  # View plane
        point_left = DB.XYZ(min(first.X, second.X), min(first.Y, second.Y), 0)
        point_right = DB.XYZ(max(first.X, second.X), max(first.Y, second.Y), 0)

    elif round(direction.Y - direction.Z, 5) == 0:  # Section in X
        point_left, point_right = transform_point_for_section(
            first, second, side='Y',
            flip_direction=int(direction.X) == -1)

    elif round(direction.X - direction.Z, 5) == 0:  # Section in Y
        point_left, point_right = transform_point_for_section(
            first, second, side='X',
            flip_direction=int(direction.Y) == 1)

    else:
        raise NotImplemented("3D and slope section doesn't work")  # FIXME
    return point_left, point_right


def user_selection():
    selection_filter = MySelectionFilter1()
    walls = uidoc.Selection.PickElementsByRectangle(selection_filter, 'select walls')
    return walls


def return_user_selection():
    elements = user_selection()
    el_id = List[DB.ElementId]([el.Id for el in elements])
    uidoc.Selection.SetElementIds(el_id)


def open_another_file():
    paths = [
        r'C:\Учеба\Дин\Observation_Tower.0003.rvt',
        r'C:\Users\appol\Desktop\Проект1.rvt',
        r'C:\Учеба\Дин\Observation_Tower.rvt',
        r'C:\Users\appol\Desktop\Lahta_WD_BIM_S_KJ_detached.rvt'
    ]
    paths = paths[:-1]
    open_options = DB.OpenOptions()
    report = []

    for path in paths:
        file_path = DB.FilePath(path)
        cur_open_option = get_option_without_links_if_model_workshared_else_none(file_path) or open_options
        family_doc = app.OpenDocumentFile(file_path, cur_open_option)
        get_list_workset(family_doc)
        walls = DB.FilteredElementCollector(family_doc).OfClass(DB.Wall).WhereElementIsNotElementType().ToElements()
        walls_number = len(walls)
        report.append("File {} contains {} walls".format(os.path.basename(path), walls_number))
        if not family_doc.Equals(doc):
            family_doc.Close(False)

    return report


def get_list_workset(family_doc):
    worksets = DB.FilteredWorksetCollector(family_doc).OfKind(DB.WorksetKind.UserWorkset).ToWorksets()
    # print worksets

    for workset in sorted(worksets, key=lambda x: x.Name):
        print workset.IsOpen, '\t\t', workset.Name


def get_option_without_links_if_model_workshared_else_none(file_path):
    try:
        worksets = DB.WorksharingUtils.GetUserWorksetInfo(file_path)
    except Ex.CentralModelException:
        'The model is not workshared'
        return

    workset_ids = [workset.Id for workset in worksets if not workset.Name.lower().startswith('00_link_')]
    open_config = DB.WorksetConfiguration(DB.WorksetConfigurationOption.CloseAllWorksets)
    open_config.Open(workset_ids)

    open_option = DB.OpenOptions()
    open_option.SetOpenWorksetsConfiguration(open_config)
    # open_option.DetachFromCentralOption = DB.DetachFromCentralOption.DetachAndDiscardWorksets
    return open_option


def group_param():
    group = UnwrapElement(IN[4])
    group_type_id = group.GetTypeId()
    group_type = doc.GetElement(group_type_id)
    for par in group_type.Parameters:
        print '', par.Definition.Name
        print '\t\t', get_value(par)
    return group_type


def get_value(parameter):
    if parameter.StorageType == DB.StorageType.String:
        return parameter.AsString()
    if parameter.StorageType == DB.StorageType.ElementId:
        return doc.GetElement(parameter.AsElementId())
    if parameter.StorageType == DB.StorageType.Integer:
        return parameter.AsInteger()
    if parameter.StorageType == DB.StorageType.Double:
        return parameter.AsDouble()


def project_param():
    project_info = DB.FilteredElementCollector(doc)
    project_info.OfCategory(DB.BuiltInCategory.OST_ProjectInformation)
    project_info = project_info.ToElements()[0]

    for par in project_info.Parameters:
        print par.Definition.Name, par.StorageType

    return project_info


def filter_collector():
    bics = [DB.BuiltInCategory.OST_StructuralColumns,
            DB.BuiltInCategory.OST_StructuralFraming,
            DB.BuiltInCategory.OST_StructuralFoundation]

    a = List[DB.ElementFilter]()
    for bic in bics:
        a.Add(DB.ElementCategoryFilter(bic))

    category_filter = DB.LogicalOrFilter(a)
    family_instance_filter = DB.LogicalAndFilter(category_filter, DB.ElementClassFilter(DB.FamilyInstance))

    b = List[DB.ElementFilter]()
    cats = [DB.Wall, DB.Floor]
    for cat in cats:
        b.Add(DB.ElementClassFilter(cat))
    b.Add(family_instance_filter)

    class_filter = DB.LogicalOrFilter(b)

    collector = DB.FilteredElementCollector(doc)
    collector.WherePasses(class_filter)
    return collector


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')
    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')

    print 'Time: {:.5f}'.format(time.time() - start)
