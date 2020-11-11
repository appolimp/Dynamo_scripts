# coding=utf-8
from base.wrapper import transaction, doc
from base.exeption import ScriptError

from my_class.my_callout import MyCalloutCreator
from my_class.my_elem import MyElemFactory
from my_class.my_section import MyAlongSectionCreator, MyAcrossSectionCreator
from my_class.my_selection import get_preselected_elems_or_invite

import logging


@transaction
def main():
    """
    Create Callout to selected elements

    Get pre-selected elements or invite user to select it

    Get input from dynamo:

    - OFFSET: type(float), Offset value to callout
    - ROTATED: type(bool), Rotate or not callout view
    """

    elems = get_preselected_elems_or_invite()
    OFFSET = IN[0]
    ROTATED = IN[1]

    IS_CREATE_ALONG_1 = IN[2]
    IS_CREATE_ALONG_2 = IN[3]
    IS_CREATE_ACROSS_1 = IN[4]

    for elem in elems:
        my_elem = MyElemFactory.get_geom_to_element(elem)
        need_update = MyElemFactory.is_valid(elem.Category)
        cal = MyCalloutCreator(my_elem, need_update).create_callout_on_view(
            doc.ActiveView, rotated=ROTATED, offset=OFFSET)

        if IS_CREATE_ALONG_1:
            MyAlongSectionCreator(my_elem).create_section()

        if IS_CREATE_ALONG_2:
            MyAlongSectionCreator(my_elem).create_section(flip=True)

        if IS_CREATE_ACROSS_1:
            MyAcrossSectionCreator(my_elem).create_section()


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.DEBUG,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
