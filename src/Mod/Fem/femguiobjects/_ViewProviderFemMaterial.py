# ***************************************************************************
# *   Copyright (c) 2013 Juergen Riegel <FreeCAD@juergen-riegel.net>        *
# *   Copyright (c) 2016 Bernd Hahnebach <bernd@bimstatik.org>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

__title__ = "FreeCAD FEM material ViewProvider for the document object"
__author__ = "Juergen Riegel, Bernd Hahnebach"
__url__ = "http://www.freecadweb.org"

## @package _ViewProviderFemMaterial
#  \ingroup FEM
#  \brief FreeCAD FEM _ViewProviderFemMaterial

import FreeCAD
import FreeCADGui
import FemGui  # needed to display the icons in TreeView
False if False else FemGui.__name__  # dummy usage of FemGui for flake8, just returns 'FemGui'

# for the panel
from FreeCAD import Units
from . import FemSelectionWidgets
from PySide import QtCore
from PySide import QtGui
import sys
if sys.version_info.major >= 3:
    unicode = str


class _ViewProviderFemMaterial:
    "A View Provider for the FemMaterial object"

    def __init__(self, vobj):
        vobj.Proxy = self

    def getIcon(self):
        return ":/icons/fem-material.svg"

    def attach(self, vobj):
        self.ViewObject = vobj
        self.Object = vobj.Object

    def updateData(self, obj, prop):
        return

    def onChanged(self, vobj, prop):
        return

    def setEdit(self, vobj, mode):
        # hide all meshes
        for o in FreeCAD.ActiveDocument.Objects:
            if o.isDerivedFrom("Fem::FemMeshObject"):
                o.ViewObject.hide()
        # show task panel
        taskd = _TaskPanelFemMaterial(self.Object)
        taskd.obj = vobj.Object
        FreeCADGui.Control.showDialog(taskd)
        return True

    def unsetEdit(self, vobj, mode):
        FreeCADGui.Control.closeDialog()
        return True

    # overwrite the doubleClicked of material object python to make sure no other Material taskd
    # (and thus no selection observer) is still active
    def doubleClicked(self, vobj):
        guidoc = FreeCADGui.getDocument(vobj.Object.Document)
        # check if another VP is in edit mode
        # https://forum.freecadweb.org/viewtopic.php?t=13077#p104702
        if not guidoc.getInEdit():
            guidoc.setEdit(vobj.Object.Name)
        else:
            from PySide.QtGui import QMessageBox
            message = 'Active Task Dialog found! Please close this one before opening  a new one!'
            QMessageBox.critical(None, "Error in tree view", message)
            FreeCAD.Console.PrintError(message + '\n')
        return True

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class _TaskPanelFemMaterial:
    '''The editmode TaskPanel for FemMaterial objects'''

    def __init__(self, obj):

        FreeCAD.Console.PrintMessage('\n')  # empty line on start task panel
        self.obj = obj
        self.material = self.obj.Material  # FreeCAD material dictionary of current material
        self.card_path = ''
        self.materials = {}  # { card_path : FreeCAD material dict, ... }
        self.cards = {}  # { card_path : card_names, ... }
        self.icons = {}  # { card_path : icon_path, ... }
        # mat_card is the FCMat file
        # card_name is the file name of the mat_card
        # card_path is the whole file path of the mat_card
        # material_name is the value of the key name in FreeCAD material dictionary
        # they might not match because of special letters in the material_name
        # which are changed in the card_name to english standard characters
        self.has_transient_mat = False

        # parameter widget
        self.parameterWidget = FreeCADGui.PySideUic.loadUi(
            FreeCAD.getHomePath() + "Mod/Fem/Resources/ui/Material.ui"
        )
        # globals
        QtCore.QObject.connect(
            self.parameterWidget.cb_materials,
            QtCore.SIGNAL("activated(int)"),
            self.choose_material
        )
        QtCore.QObject.connect(
            self.parameterWidget.chbu_allow_edit,
            QtCore.SIGNAL("clicked()"),
            self.toggleInputFieldsReadOnly
        )
        QtCore.QObject.connect(
            self.parameterWidget.pushButton_editMat,
            QtCore.SIGNAL("clicked()"),
            self.edit_material
        )
        # basic properties must be provided
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_density,
            QtCore.SIGNAL("editingFinished()"),
            self.density_changed
        )
        # mechanical properties
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_young_modulus,
            QtCore.SIGNAL("editingFinished()"),
            self.ym_changed
        )
        QtCore.QObject.connect(
            self.parameterWidget.spinBox_poisson_ratio,
            QtCore.SIGNAL("editingFinished()"),
            self.pr_changed
        )
        # thermal properties
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_thermal_conductivity,
            QtCore.SIGNAL("editingFinished()"),
            self.tc_changed
        )
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_expansion_coefficient,
            QtCore.SIGNAL("editingFinished()"),
            self.tec_changed
        )
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_specific_heat,
            QtCore.SIGNAL("editingFinished()"),
            self.sh_changed
        )
        # fluidic properties, only volumetric thermal expansion coeff makes sense
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_kinematic_viscosity,
            QtCore.SIGNAL("editingFinished()"),
            self.kinematic_viscosity_changed
        )
        QtCore.QObject.connect(
            self.parameterWidget.input_fd_vol_expansion_coefficient,
            QtCore.SIGNAL("editingFinished()"),
            self.vtec_changed
        )

        # init all parameter input files with read only
        self.parameterWidget.chbu_allow_edit.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.toggleInputFieldsReadOnly()

        # hide some groupBox according to material category
        self.parameterWidget.label_category.setText(self.obj.Category)
        if self.obj.Category == 'Fluid':
            self.parameterWidget.groupBox_mechanical.setVisible(0)
            self.parameterWidget.label_expansion_coefficient.setVisible(0)
            self.parameterWidget.input_fd_expansion_coefficient.setVisible(0)
        else:
            self.parameterWidget.groupBox_fluidic.setVisible(0)
            self.parameterWidget.label_vol_expansion_coefficient.setVisible(0)
            self.parameterWidget.input_fd_vol_expansion_coefficient.setVisible(0)

        # get all available materials (fill self.materials, self.cards and self.icons)
        from materialtools.cardutils import import_materials as getmats
        self.materials, self.cards, self.icons = getmats()
        # fill the material comboboxes with material cards
        self.add_cards_to_combo_box()

        # search for exact this mat_card in all known cards, choose the current material
        self.card_path = self.get_material_card(self.material)
        FreeCAD.Console.PrintLog('card_path: {}'.format(self.card_path))
        if not self.card_path:
            # we have not found our material in self.materials dict :-(
            # we're going to add a user-defined temporary material: a document material
            FreeCAD.Console.PrintMessage(
                "Previously used material card can not be found in material directories. "
                "Add document material.\n"
            )
            self.card_path = '_document_material'
            self.materials[self.card_path] = self.material
            self.parameterWidget.cb_materials.addItem(
                QtGui.QIcon(":/icons/help-browser.svg"),
                self.card_path,
                self.card_path
            )
            index = self.parameterWidget.cb_materials.findData(self.card_path)
            # print(index)
            # fill input fields and set the current material in the cb widget
            self.choose_material(index)
        else:
            # we found our exact material in self.materials dict :-)
            FreeCAD.Console.PrintLog(
                "Previously used material card was found in material directories. "
                "We will use this material.\n"
            )
            index = self.parameterWidget.cb_materials.findData(self.card_path)
            # print(index)
            # fill input fields and set the current material in the cb widget
            self.choose_material(index)

        # geometry selection widget
        self.selectionWidget = FemSelectionWidgets.GeometryElementsSelection(
            obj.References,
            ['Solid', 'Face', 'Edge'],
            False
        )  # start with Solid in list!

        # form made from param and selection widget
        self.form = [self.parameterWidget, self.selectionWidget]

        # check references, has to be after initialisation of selectionWidget
        self.selectionWidget.has_equal_references_shape_types()

    # leave task panel ***************************************************************************
    def accept(self):
        # print(self.material)
        if self.selectionWidget.has_equal_references_shape_types():
            self.do_not_set_thermal_zeros()
            from materialtools.cardutils import check_mat_units as checkunits
            if checkunits(self.material) is True:
                self.obj.Material = self.material
                self.obj.References = self.selectionWidget.references
            else:
                error_message = (
                    'Due to some wrong material quantity units in the changed '
                    'material data, the task panel changes where not accepted.\n'
                )
                FreeCAD.Console.PrintError(error_message)
                QtGui.QMessageBox.critical(None, "Material data not changed", error_message)
        self.recompute_and_set_back_all()
        return True

    def reject(self):
        self.recompute_and_set_back_all()
        return True

    def recompute_and_set_back_all(self):
        doc = FreeCADGui.getDocument(self.obj.Document)
        doc.Document.recompute()
        self.selectionWidget.setback_listobj_visibility()
        if self.selectionWidget.sel_server:
            FreeCADGui.Selection.removeObserver(self.selectionWidget.sel_server)
        doc.resetEdit()

    def do_not_set_thermal_zeros(self):
        ''' thermal material parameter are set to 0.0 if not available
        this leads to wrong material values and to not finding the card
        on reopen the task pane, thus do not write thermal parameter,
        if they are 0.0
        '''
        if Units.Quantity(self.material['ThermalConductivity']) == 0.0:
            self.material.pop('ThermalConductivity', None)
            FreeCAD.Console.PrintMessage(
                'Zero ThermalConductivity value. '
                'This parameter is not saved in the material data.\n'
            )
        if Units.Quantity(self.material['ThermalExpansionCoefficient']) == 0.0:
            self.material.pop('ThermalExpansionCoefficient', None)
            FreeCAD.Console.PrintMessage(
                'Zero ThermalExpansionCoefficient value. '
                'This parameter is not saved in the material data.\n'
            )
        if Units.Quantity(self.material['SpecificHeat']) == 0.0:
            self.material.pop('SpecificHeat', None)
            FreeCAD.Console.PrintMessage(
                'Zero SpecificHeat value. '
                'This parameter is not saved in the material data.\n'
            )

    # choose material ****************************************************************************
    def get_material_card(self, material):
        for a_mat in self.materials:
            unmatched_items = set(self.materials[a_mat].items()) ^ set(material.items())
            # print(a_mat + '  -->  unmatched_items = ' + str(len(unmatched_items)))
            # if len(unmatched_items) < 4:
            #     print(unmatched_items)
            if len(unmatched_items) == 0:
                return a_mat
        return ""

    def choose_material(self, index):
        if index < 0:
            return
        self.card_path = self.parameterWidget.cb_materials.itemData(index)  # returns whole path
        FreeCAD.Console.PrintMessage(
            'choose_material in FEM material task panel:\n'
            '    {}\n'.format(self.card_path)
        )
        self.material = self.materials[self.card_path]
        self.check_material_keys()
        self.set_mat_params_in_input_fields(self.material)
        self.parameterWidget.cb_materials.setCurrentIndex(index)  # set after input fields
        gen_mat_desc = ""
        gen_mat_name = ""
        if 'Description' in self.material:
            gen_mat_desc = self.material['Description']
        if 'Name' in self.material:
            gen_mat_name = self.material['Name']
        self.parameterWidget.l_mat_description.setText(gen_mat_desc)
        self.parameterWidget.l_mat_name.setText(gen_mat_name)
        # print('choose_material: done')

    def set_transient_material(self):
        self.card_path = '_transient_material'
        self.materials[self.card_path] = self.material  # = the current input fields data
        index = self.parameterWidget.cb_materials.findData(self.card_path)
        self.choose_material(index)

    def add_transient_material(self):
        self.has_transient_mat = True
        self.card_path = '_transient_material'
        self.parameterWidget.cb_materials.addItem(
            QtGui.QIcon(":/icons/help-browser.svg"),
            self.card_path,
            self.card_path
        )
        self.set_transient_material()

    # how to edit a material *********************************************************************
    def edit_material(self):
        # opens the material editor to choose a material or edit material params
        import MaterialEditor
        if self.card_path not in self.cards:
            FreeCAD.Console.PrintLog(
                'Card path not in cards, material dict will be used to open Material Editor.\n'
            )
            new_material_params = MaterialEditor.editMaterial(material=self.material)
        else:
            new_material_params = MaterialEditor.editMaterial(card_path=self.card_path)
        # material editor returns the mat_dict only, not a card_path
        # if the material editor was canceled a empty dict will be returned
        # do not change the self.material
        # check if dict is not empty (do not use 'is True')
        if new_material_params:
            # check material quantity units
            from materialtools.cardutils import check_mat_units as checkunits
            if checkunits(new_material_params) is True:
                self.material = new_material_params
                self.card_path = self.get_material_card(self.material)
                # print('card_path: ' + self.card_path)
                self.check_material_keys()
                self.set_mat_params_in_input_fields(self.material)
                if not self.card_path:
                    FreeCAD.Console.PrintMessage(
                        "Material card chosen by the material editor "
                        "was not found in material directories.\n"
                        "Either the card does not exist or some material "
                        "parameter where changed in material editor.\n"
                    )
                    if self.has_transient_mat is False:
                        self.add_transient_material()
                    else:
                        self.set_transient_material()
                else:
                    # we found our exact material in self.materials dict :-)
                    FreeCAD.Console.PrintLog(
                        "Material card chosen by the material editor "
                        "was found in material directories. "
                        "The found material card will be used.\n"
                    )
                    index = self.parameterWidget.cb_materials.findData(self.card_path)
                    # print(index)
                    # set the current material in the cb widget
                    self.choose_material(index)
            else:
                error_message = (
                    'Due to some wrong material quantity units in data passed '
                    'by the material editor, the material data was not changed.\n'
                )
                FreeCAD.Console.PrintError(error_message)
                QtGui.QMessageBox.critical(None, "Material data not changed", error_message)
        else:
            FreeCAD.Console.PrintLog(
                'No changes where made by the material editor.\n'
            )

    def toggleInputFieldsReadOnly(self):
        if self.parameterWidget.chbu_allow_edit.isChecked():
            self.parameterWidget.input_fd_density.setReadOnly(False)
            self.parameterWidget.input_fd_young_modulus.setReadOnly(False)
            self.parameterWidget.spinBox_poisson_ratio.setReadOnly(False)
            self.parameterWidget.input_fd_thermal_conductivity.setReadOnly(False)
            self.parameterWidget.input_fd_expansion_coefficient.setReadOnly(False)
            self.parameterWidget.input_fd_specific_heat.setReadOnly(False)
            self.parameterWidget.input_fd_kinematic_viscosity.setReadOnly(False)
            self.parameterWidget.input_fd_vol_expansion_coefficient.setReadOnly(False)
        else:
            self.parameterWidget.input_fd_density.setReadOnly(True)
            self.parameterWidget.input_fd_young_modulus.setReadOnly(True)
            self.parameterWidget.spinBox_poisson_ratio.setReadOnly(True)
            self.parameterWidget.input_fd_thermal_conductivity.setReadOnly(True)
            self.parameterWidget.input_fd_expansion_coefficient.setReadOnly(True)
            self.parameterWidget.input_fd_specific_heat.setReadOnly(True)
            self.parameterWidget.input_fd_kinematic_viscosity.setReadOnly(True)
            self.parameterWidget.input_fd_vol_expansion_coefficient.setReadOnly(True)

    # material parameter input fields ************************************************************
    def check_material_keys(self):
        # FreeCAD units definition is at file end of src/Base/Unit.cpp
        if not self.material:
            FreeCAD.Console.PrintMessage('For some reason all material data is empty!\n')
            self.material['Name'] = 'Empty'
        if 'Density' in self.material:
            if 'Density' not in str(Units.Unit(self.material['Density'])):
                FreeCAD.Console.PrintMessage(
                    'Density in material data seems to have no unit '
                    'or a wrong unit (reset the value): {}\n'
                    .format(self.material['Name'])
                )
                self.material['Density'] = '0 kg/m^3'
        else:
            FreeCAD.Console.PrintMessage(
                'Density not found in material data of: {}\n'
                .format(self.material['Name'])
            )
            self.material['Density'] = '0 kg/m^3'
        if self.obj.Category == 'Solid':
            # mechanical properties
            if 'YoungsModulus' in self.material:
                # unit type of YoungsModulus is Pressure
                if 'Pressure' not in str(Units.Unit(self.material['YoungsModulus'])):
                    FreeCAD.Console.PrintMessage(
                        'YoungsModulus in material data seems to have no unit '
                        'or a wrong unit (reset the value): {}\n'
                        .format(self.material['Name'])
                    )
                    self.material['YoungsModulus'] = '0 MPa'
            else:
                FreeCAD.Console.PrintMessage(
                    'YoungsModulus not found in material data of: {}\n'
                    .format(self.material['Name'])
                )
                self.material['YoungsModulus'] = '0 MPa'
            if 'PoissonRatio' in self.material:
                # PoissonRatio does not have a unit, but it is checked it there is no value at all
                try:
                    float(self.material['PoissonRatio'])
                except:
                    FreeCAD.Console.PrintMessage(
                        'PoissonRatio has wrong or no data (reset the value): {}\n'
                        .format(self.material['PoissonRatio'])
                    )
                    self.material['PoissonRatio'] = '0'
            else:
                FreeCAD.Console.PrintMessage(
                    'PoissonRatio not found in material data of: {}\n'
                    .format(self.material['Name'])
                )
                self.material['PoissonRatio'] = '0'
        if self.obj.Category == 'Fluid':
            # Fluidic properties
            if 'KinematicViscosity' in self.material:
                ki_vis = self.material['KinematicViscosity']
                if 'KinematicViscosity' not in str(Units.Unit(ki_vis)):
                    FreeCAD.Console.PrintMessage(
                        'KinematicViscosity in material data seems to have no unit '
                        'or a wrong unit (reset the value): {}\n'
                        .format(self.material['Name'])
                    )
                    self.material['KinematicViscosity'] = '0 m^2/s'
            else:
                FreeCAD.Console.PrintMessage(
                    'KinematicViscosity not found in material data of: {}\n'
                    .format(self.material['Name'])
                )
                self.material['KinematicViscosity'] = '0 m^2/s'
            if 'VolumetricThermalExpansionCoefficient' in self.material:
                # unit type VolumetricThermalExpansionCoefficient is ThermalExpansionCoefficient
                vol_ther_ex_co = self.material['VolumetricThermalExpansionCoefficient']
                if 'VolumetricThermalExpansionCoefficient' not in str(Units.Unit(vol_ther_ex_co)):
                    FreeCAD.Console.PrintMessage(
                        'VolumetricThermalExpansionCoefficient in material data '
                        'seems to have no unit or a wrong unit (reset the value): {}\n'
                        .format(self.material['Name'])
                    )
                    self.material['VolumetricThermalExpansionCoefficient'] = '0 m/m/K'
            else:
                FreeCAD.Console.PrintMessage(
                    'VolumetricThermalExpansionCoefficient not found in material data of: {}\n'
                    .format(self.material['Name'])
                )
                self.material['VolumetricThermalExpansionCoefficient'] = '0 m/m/K'
        # Thermal properties
        if 'ThermalConductivity' in self.material:
            if 'ThermalConductivity' not in str(Units.Unit(self.material['ThermalConductivity'])):
                FreeCAD.Console.PrintMessage(
                    'ThermalConductivity in material data seems to have no unit '
                    'or a wrong unit (reset the value): {}\n'
                    .format(self.material['Name'])
                )
                self.material['ThermalConductivity'] = '0 W/m/K'
        else:
            FreeCAD.Console.PrintMessage(
                'ThermalConductivity not found in material data of: {}\n'
                .format(self.material['Name'])
            )
            self.material['ThermalConductivity'] = '0 W/m/K'
        if 'ThermalExpansionCoefficient' in self.material:
            the_ex_co = self.material['ThermalExpansionCoefficient']
            if 'ThermalExpansionCoefficient' not in str(Units.Unit(the_ex_co)):
                FreeCAD.Console.PrintMessage(
                    'ThermalExpansionCoefficient in material data seems to have no unit '
                    'or a wrong unit (reset the value): {}\n'
                    .format(self.material['Name'])
                )
                self.material['ThermalExpansionCoefficient'] = '0 um/m/K'
        else:
            FreeCAD.Console.PrintMessage(
                'ThermalExpansionCoefficient not found in material data of: {}\n'
                .format(self.material['Name'])
            )
            self.material['ThermalExpansionCoefficient'] = '0 um/m/K'
        if 'SpecificHeat' in self.material:
            if 'SpecificHeat' not in str(Units.Unit(self.material['SpecificHeat'])):
                FreeCAD.Console.PrintMessage(
                    'SpecificHeat in material data seems to have no unit '
                    'or a wrong unit (reset the value): {}\n'
                    .format(self.material['Name'])
                )
                self.material['SpecificHeat'] = '0 J/kg/K'
        else:
            FreeCAD.Console.PrintMessage(
                'SpecificHeat not found in material data of: {}\n'
                .format(self.material['Name'])
            )
            self.material['SpecificHeat'] = '0 J/kg/K'
        FreeCAD.Console.PrintMessage('\n')

    # mechanical input fields
    def ym_changed(self):
        # FreeCADs standard unit for stress is kPa
        value = self.parameterWidget.input_fd_young_modulus.property("rawValue")
        old_ym = Units.Quantity(self.material['YoungsModulus']).getValueAs("kPa")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_ym) / value < 1 + variation):
                # YoungsModulus has changed
                material = self.material
                material['YoungsModulus'] = unicode(value) + " kPa"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def density_changed(self):
        # FreeCADs standard unit for density is kg/mm^3
        value = self.parameterWidget.input_fd_density.property("rawValue")
        old_density = Units.Quantity(self.material['Density']).getValueAs("kg/m^3")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_density) / value < 1 + variation):
                # density has changed
                material = self.material
                value_in_kg_per_m3 = value * 1e9
                # SvdW:Keep density in SI units for easier readability
                material['Density'] = unicode(value_in_kg_per_m3) + " kg/m^3"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def pr_changed(self):
        value = self.parameterWidget.spinBox_poisson_ratio.value()
        old_pr = Units.Quantity(self.material['PoissonRatio'])
        variation = 0.001
        if value:
            if not (1 - variation < float(old_pr) / value < 1 + variation):
                # PoissonRatio has changed
                material = self.material
                material['PoissonRatio'] = unicode(value)
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()
        elif value == 0:
            # PoissonRatio was set to 0.0 what is possible
            material = self.material
            material['PoissonRatio'] = unicode(value)
            self.material = material
            if self.has_transient_mat is False:
                self.add_transient_material()
            else:
                self.set_transient_material()

    # thermal input fields
    def tc_changed(self):
        value = self.parameterWidget.input_fd_thermal_conductivity.property("rawValue")
        old_tc = Units.Quantity(self.material['ThermalConductivity']).getValueAs("W/m/K")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_tc) / value < 1 + variation):
                # ThermalConductivity has changed
                material = self.material
                value_in_W_per_mK = value * 1e-3  # To compensate for use of SI units
                material['ThermalConductivity'] = unicode(value_in_W_per_mK) + " W/m/K"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def tec_changed(self):
        value = self.parameterWidget.input_fd_expansion_coefficient.property("rawValue")
        old_tec = Units.Quantity(
            self.material['ThermalExpansionCoefficient']
        ).getValueAs("um/m/K")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_tec) / value < 1 + variation):
                # ThermalExpansionCoefficient has changed
                material = self.material
                value_in_um_per_mK = value * 1e6  # To compensate for use of SI units
                material['ThermalExpansionCoefficient'] = unicode(value_in_um_per_mK) + " um/m/K"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def sh_changed(self):
        value = self.parameterWidget.input_fd_specific_heat.property("rawValue")
        old_sh = Units.Quantity(self.material['SpecificHeat']).getValueAs("J/kg/K")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_sh) / value < 1 + variation):
                # SpecificHeat has changed
                material = self.material
                value_in_J_per_kgK = value * 1e-6  # To compensate for use of SI units
                material['SpecificHeat'] = unicode(value_in_J_per_kgK) + " J/kg/K"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    # fluidic input fields
    def vtec_changed(self):
        value = self.parameterWidget.input_fd_vol_expansion_coefficient.property("rawValue")
        old_vtec = Units.Quantity(
            self.material['VolumetricThermalExpansionCoefficient']
        ).getValueAs("m/m/K")
        variation = 0.001
        if value:
            if not (1 - variation < float(old_vtec) / value < 1 + variation):
                # VolumetricThermalExpansionCoefficient has changed
                material = self.material
                value_in_one_per_K = unicode(value) + " m/m/K"
                material['VolumetricThermalExpansionCoefficient'] = value_in_one_per_K
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def kinematic_viscosity_changed(self):
        value = self.parameterWidget.input_fd_kinematic_viscosity.property("rawValue")
        old_nu = Units.Quantity(self.material['KinematicViscosity']).getValueAs("m^2/s")
        variation = 0.000001
        if value:
            if not (1 - variation < float(old_nu) / value < 1 + variation):
                # KinematicViscosity has changed
                material = self.material
                value_in_m2_per_second = value
                material['KinematicViscosity'] = unicode(value_in_m2_per_second) + " m^2/s"
                self.material = material
                if self.has_transient_mat is False:
                    self.add_transient_material()
                else:
                    self.set_transient_material()

    def set_mat_params_in_input_fields(self, matmap):
        if 'YoungsModulus' in matmap:
            ym_new_unit = "MPa"
            ym = FreeCAD.Units.Quantity(matmap['YoungsModulus'])
            ym_with_new_unit = ym.getValueAs(ym_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(ym_with_new_unit, ym_new_unit))
            self.parameterWidget.input_fd_young_modulus.setText(q.UserString)
        if 'PoissonRatio' in matmap:
            self.parameterWidget.spinBox_poisson_ratio.setValue(float(matmap['PoissonRatio']))
        # Fluidic properties
        if 'KinematicViscosity' in matmap:
            nu_new_unit = "m^2/s"
            nu = FreeCAD.Units.Quantity(matmap['KinematicViscosity'])
            nu_with_new_unit = nu.getValueAs(nu_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(nu_with_new_unit, nu_new_unit))
            self.parameterWidget.input_fd_kinematic_viscosity.setText(q.UserString)
        # For isotropic materials the volumetric thermal expansion coefficient
        # is three times the linear coefficient:
        if 'VolumetricThermalExpansionCoefficient' in matmap:  # linear, only for solid
            vtec_new_unit = "m/m/K"
            vtec = FreeCAD.Units.Quantity(matmap['VolumetricThermalExpansionCoefficient'])
            vtec_with_new_unit = vtec.getValueAs(vtec_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(vtec_with_new_unit, vtec_new_unit))
            self.parameterWidget.input_fd_vol_expansion_coefficient.setText(q.UserString)
        if 'Density' in matmap:
            density_new_unit = "kg/m^3"
            density = FreeCAD.Units.Quantity(matmap['Density'])
            density_with_new_unit = density.getValueAs(density_new_unit)
            # self.parameterWidget.input_fd_density.setText(
            #     "{} {}".format(density_with_new_unit, density_new_unit)
            # )
            q = FreeCAD.Units.Quantity("{} {}".format(density_with_new_unit, density_new_unit))
            self.parameterWidget.input_fd_density.setText(q.UserString)
        # thermal properties
        if 'ThermalConductivity' in matmap:
            tc_new_unit = "W/m/K"
            tc = FreeCAD.Units.Quantity(matmap['ThermalConductivity'])
            tc_with_new_unit = tc.getValueAs(tc_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(tc_with_new_unit, tc_new_unit))
            self.parameterWidget.input_fd_thermal_conductivity.setText(q.UserString)
        if 'ThermalExpansionCoefficient' in matmap:  # linear, only for solid
            tec_new_unit = "um/m/K"
            tec = FreeCAD.Units.Quantity(matmap['ThermalExpansionCoefficient'])
            tec_with_new_unit = tec.getValueAs(tec_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(tec_with_new_unit, tec_new_unit))
            self.parameterWidget.input_fd_expansion_coefficient.setText(q.UserString)
        if 'SpecificHeat' in matmap:
            sh_new_unit = "J/kg/K"
            sh = FreeCAD.Units.Quantity(matmap['SpecificHeat'])
            sh_with_new_unit = sh.getValueAs(sh_new_unit)
            q = FreeCAD.Units.Quantity("{} {}".format(sh_with_new_unit, sh_new_unit))
            self.parameterWidget.input_fd_specific_heat.setText(q.UserString)

    # fill the combo box with cards **************************************************************
    def add_cards_to_combo_box(self):
        # fill combobox, in combo box the card name is used not the material name
        self.parameterWidget.cb_materials.clear()

        mat_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Material/Cards")
        sort_by_resources = mat_prefs.GetBool("SortByResources", False)

        card_name_list = []  # [ [card_name, card_path, icon_path], ... ]

        if sort_by_resources is True:
            for a_path in sorted(self.materials.keys()):
                card_name_list.append([self.cards[a_path], a_path, self.icons[a_path]])
        else:
            card_names_tmp = {}
            for path, name in self.cards.items():
                card_names_tmp[name] = path
            for a_name in sorted(card_names_tmp.keys()):
                a_path = card_names_tmp[a_name]
                card_name_list.append([a_name, a_path, self.icons[a_path]])

        for mat in card_name_list:
            self.parameterWidget.cb_materials.addItem(QtGui.QIcon(mat[2]), mat[0], mat[1])
            # the whole card path is added to the combo box to make it unique
            # see def choose_material:
            # for assignment of self.card_path the path form the parameterWidget ist used
