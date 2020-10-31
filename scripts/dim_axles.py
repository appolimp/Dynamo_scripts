# coding=utf-8
from base.wrapper import transaction, doc, DB, clr, uidoc
from base.exeption import ScriptError
from base.selection import get_selected_by_cat
from Autodesk.Revit.UI.Selection import ISelectionFilter
import logging


SECTION_TYPE = [DB.ViewType.Section, DB.ViewType.Elevation]


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


class OutLineDim:
    FIRST_OFFSET_1 = 20
    NEXT_OFFSET_1 = 10

    def __init__(self, origin, normal):
        self.origin = origin
        self.normal = normal

        self.scale = doc.ActiveView.Scale
        self.__offset = self._offset_coroutine()

    @classmethod
    def create_by_two_point_and_normal(cls, normal):
        point = get_user_point()
        side_point = get_user_point()

        sign_normal = cls._calc_direction_by_side(normal, side_point - point)

        return cls(point, sign_normal)

    @staticmethod
    def _calc_direction_by_side(normal, side):
        if doc.ActiveView.ViewType in SECTION_TYPE:
            normal = normal if side.Z > 0 else -normal
        else:
            dir_norm = normal.CrossProduct(DB.XYZ.BasisZ)
            side_z = dir_norm.CrossProduct(side).Z
            normal = normal if side_z > 0 else -normal

        logging.debug('Normal calculated {}'.format(normal))
        return normal

    def get_outline(self):
        view_normal = doc.ActiveView.ViewDirection
        direction = self.normal.CrossProduct(view_normal)

        origin = self.origin + self.normal * self._offset

        out_line = DB.Line.CreateUnbound(origin, direction)

        logging.debug('Outline created: origin {}; direction {}'.format(origin, direction))
        return out_line

    @property
    def _offset(self):
        return next(self.__offset)

    def _offset_coroutine(self):
        total_sum = self._calc_offset_by_value(self.FIRST_OFFSET_1)

        while True:
            yield total_sum
            total_sum += self._calc_offset_by_value(self.NEXT_OFFSET_1)

    def _calc_offset_by_value(self, value):
        new_value = value * self.scale / 304.8

        logging.debug('Calc offset value {} mm for scale 1:{} == {} ft'.format(value, self.scale, new_value))
        return new_value


class AxlesDim:
    def __init__(self, axles):
        self.axles = axles

        one_curve = axles[0].GetCurvesInView(DB.DatumExtentType.ViewSpecific, doc.ActiveView)[0]
        self.direction = one_curve.Direction

    @property
    def as_ref_arr(self):
        ref_arr = DB.ReferenceArray()
        for axis in self.axles:
            ref_arr.Append(DB.Reference(axis))
        logging.debug('ReferenceArray for {} grid was created'.format(len(self.axles)))
        return ref_arr

    @classmethod
    def get_by_user(cls):
        axles = get_selected_by_cat(DB.BuiltInCategory.OST_Grids, as_list=True)
        logging.info('User pre-selected {} axles'.format(len(axles)))

        if len(axles) < 1:
            axles = user_selection_by_cat(DB.BuiltInCategory.OST_Grids)

        return AxlesDim(axles)

    def crop_and_bubble(self, crop_line, bubble_modify=True):
        for axis in self.axles:
            AxisCrop(axis).modify_axis(crop_line, bubble_modify)

        logging.info(
            '{} axles was cropped and {}updated bubbles'.format(len(self.axles), '' if bubble_modify else 'not '))

    def get_corners(self):
        corners = self._get_corners()
        if len(corners) >= 2:
            return AxlesDim(corners)
        raise ScriptError('Cant found 2 corner axles')

    def _get_corners(self):
        def prod(cur_axis, other_axis):
            side = other_axis.Curve.Origin - cur_axis.Curve.Origin
            product = cur_axis.Curve.Direction.CrossProduct(side)
            return product.Z

        corners = []
        for axis in self.axles:
            z_vectors = [prod(axis, other) > 0 for other in self.axles if axis is not other]

            if all(z_vectors) or not any(z_vectors):
                logging.debug('Get corner axis "{}"'.format(axis.Name))
                corners.append(axis)

        return corners

    def __len__(self):
        return len(self.axles)


class AxisCrop:
    def __init__(self, axis):
        self.axis = axis
        self.curve = self.axis.GetCurvesInView(DB.DatumExtentType.ViewSpecific, doc.ActiveView)[0]

    def modify_axis(self, crop_line, bubble_modify=True):
        new_curve, is_start = self.crop_curve_by_line(crop_line)

        self.axis.SetCurveInView(DB.DatumExtentType.ViewSpecific, doc.ActiveView, new_curve)
        logging.debug('Axis {} curve: crop in view'.format(self.axis.Name))

        if bubble_modify:
            self._modify_bubble(is_start)

    def crop_curve_by_line(self, crop_line):
        if doc.ActiveView.ViewType in SECTION_TYPE:
            logging.debug('Line crop in section')
            return self._crop_curve_by_line_on_section(crop_line)
        else:
            logging.debug('Line crop in plane')
            return self._crop_curve_by_line_on_plane(crop_line)

    def _crop_curve_by_line_on_plane(self, crop_line):
        flatten_curve = self._make_flatten_and_extend(self.curve)
        flatten_crop_line = self._make_flatten_and_extend(crop_line)

        intersect = clr.StrongBox[DB.IntersectionResultArray]()
        is_intersect = flatten_curve.Intersect(flatten_crop_line, intersect)

        if is_intersect == DB.SetComparisonResult.Overlap:
            point = intersect.Value[0].XYZPoint
            h_point = point + DB.XYZ.BasisZ * self.curve.Origin.Z
            height_curve, is_start = self.create_line_by_closest_point(h_point)

            return height_curve, is_start

        raise ScriptError('Line not intersect')

    def _crop_curve_by_line_on_section(self, crop_line):
        origin = self.curve.Origin
        height = crop_line.Origin
        h_point = DB.XYZ(origin.X, origin.Y, height.Z)

        height_curve, is_start = self.create_line_by_closest_point(h_point)
        return height_curve, is_start

    def create_line_by_closest_point(self, point):
        start = self.curve.GetEndPoint(0)
        end = self.curve.GetEndPoint(1)

        if start.DistanceTo(point) > end.DistanceTo(point):
            is_start = False
            line = DB.Line.CreateBound(start, point)
        else:
            is_start = True
            line = DB.Line.CreateBound(point, end)

        logging.debug('Cropped line created, is_start == {}'.format(is_start))
        return line, is_start

    @staticmethod
    def _up_line_to_height(line, height):
        start_point = line.GetEndPoint(0)
        new_start = DB.XYZ(start_point.X, start_point.Y, height)

        end_point = line.GetEndPoint(1)
        new_end = DB.XYZ(end_point.X, end_point.Y, height)

        height_line = DB.Line.CreateBound(new_start, new_end)

        logging.debug('Line moved to height == {}'.format(height))
        return height_line

    def _make_flatten_and_extend(self, curve):
        BORDER = 10000

        temp_curve = curve.Clone()
        if temp_curve.IsBound:
            temp_curve.MakeUnbound()
        temp_curve.MakeBound(-BORDER, BORDER)

        flatten_line = self._up_line_to_height(temp_curve, 0)

        logging.debug('Flatten line create')
        return flatten_line

    def _modify_bubble(self, is_start):
        if is_start:
            self.axis.ShowBubbleInView(DB.DatumEnds.End0, doc.ActiveView)
            self.axis.HideBubbleInView(DB.DatumEnds.End1, doc.ActiveView)
        else:
            self.axis.ShowBubbleInView(DB.DatumEnds.End1, doc.ActiveView)
            self.axis.HideBubbleInView(DB.DatumEnds.End0, doc.ActiveView)

        temp = ('show', 'hide') if is_start else ('hide', 'show')
        logging.debug('Axis {} bubble: start - {}, end - {}'.format(self.axis.Name, *temp))


@transaction
def main():
    CREATE_DIM = IN[0]
    CREATE_DIM_SECOND = IN[1]
    CROP_AXLES = IN[2]
    EDIT_BUBBLE = IN[3]

    axles = AxlesDim.get_by_user()
    outline = OutLineDim.create_by_two_point_and_normal(axles.direction)

    dims = []
    if CREATE_DIM:
        dims = create_dim_axles_by_outline_and_axles(axles, outline, second_line=CREATE_DIM_SECOND)

    if CROP_AXLES:
        crop_line = outline.get_outline()
        axles.crop_and_bubble(crop_line, bubble_modify=EDIT_BUBBLE)

    return dims


def create_dim_axles_by_outline_and_axles(axles, outline, second_line=True):
    dim_line = outline.get_outline()
    dim = doc.Create.NewDimension(doc.ActiveView, dim_line, axles.as_ref_arr)
    dims = [dim]
    logging.info('Main dim created')

    if second_line and len(axles) > 2:
        corner_line = outline.get_outline()
        corner_axles = axles.get_corners()
        corner_dim = doc.Create.NewDimension(doc.ActiveView, corner_line, corner_axles.as_ref_arr)
        dims.append(corner_dim)
        logging.info('Second dim created')

    return dims


def user_selection_by_cat(cat):
    elem_filter = MySelectionFilter(cat)
    elems = uidoc.Selection.PickElementsByRectangle(elem_filter, 'select elements {}'.format(cat))

    logging.info('User select {}'.format(len(elems)))
    return elems


def get_user_point():
    if doc.ActiveView.ViewType in SECTION_TYPE:
        create_work_plane_on_view(doc.ActiveView)

    point = uidoc.Selection.PickPoint('Select point')
    return point


def create_work_plane_on_view(view):
    if view.SketchPlane is None:
        plane = DB.Plane.CreateByNormalAndOrigin(view.ViewDirection, view.Origin)
        sketch_plane = DB.SketchPlane.Create(doc, plane)
        view.SketchPlane = sketch_plane
        view.HideActiveWorkPlane()
        logging.debug('WorkPlane was created on view: #{}'.format(view.Id))
    else:
        logging.debug('WorkPlane already exist: #{}'.format(view.Id))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <example>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
