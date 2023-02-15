from pathlib import Path

import pandas as pd
from csvcubed.cli.inspect.metadatainputvalidator import MetadataValidator
from csvcubed.cli.inspect.metadataprinter import (
    MetadataPrinter,
    to_absolute_rdflib_file_path,
)
from csvcubed.utils.tableschema import CsvwRdfManager
from csvcubed.utils.sparql_handler.data_cube_state import DataCubeState


class Load:

    # Function that sets up dataframe and incorporates functions leveraged from csvcubed
    def buildDataFrame(self, csvw_metadata_json_path: Path) -> None:
        csvw_rdf_manager = CsvwRdfManager(csvw_metadata_json_path)

        csvw_metadata_rdf_validator = MetadataValidator(
            csvw_metadata_rdf_graph=csvw_rdf_manager.rdf_graph,
            csvw_metadata_json_path=csvw_metadata_json_path,
        )

        csvw_type = csvw_metadata_rdf_validator.detect_csvw_type()

        data_cube = DataCubeState(
            rdf_graph=csvw_rdf_manager.rdf_graph,
            csvw_json_path=csvw_rdf_manager.csvw_metadata_file_path,
        )

        metadata_printer = MetadataPrinter(
            data_cube_state=data_cube,
            code_list_state=None,
            csvw_type=csvw_type,
            csvw_metadata_rdf_graph=csvw_rdf_manager.rdf_graph,
            csvw_metadata_json_path=csvw_metadata_json_path,
        )

        metadata_printer.generate_general_results()

        dataset_uri = to_absolute_rdflib_file_path(
            metadata_printer.result_catalog_metadata.dataset_uri,
            csvw_metadata_json_path,
        )

        cube_identifiers = data_cube.get_cube_identifiers_for_data_set(
            metadata_printer.result_catalog_metadata.dataset_uri
        )
        self.dsd_components = data_cube.get_dsd_qube_components_for_csv(
            cube_identifiers.csv_url
        )
        self.cube_shape = data_cube.get_shape_for_csv(cube_identifiers.csv_url)
        csv_path = csvw_metadata_json_path.parent / cube_identifiers.csv_url

        self.data = pd.read_csv(csv_path)

        obs_val_columns = set(self.data.columns) - {
            col.title
            for component in self.dsd_components.qube_components
            for col in component.real_columns_used_in
        }
        self.obs_val_column_title = obs_val_columns.pop()

        self.dimension_column_titles = {
            col.title
            for component in self.dsd_components.qube_components
            for col in component.real_columns_used_in
            if component.property_type == "Dimension"
            and component.property != "http://purl.org/linked-data/cube#measureType"
        }

        measure_columns = {
            col.title
            for component in self.dsd_components.qube_components
            for col in component.real_columns_used_in
            if component.property_type == "Dimension"
            and component.property == "http://purl.org/linked-data/cube#measureType"
        }
        self.measure_column_title = measure_columns.pop()

        self.measure_dict = {
            str(component.property).split("/")[-1]: component.property_label
            for component in self.dsd_components.qube_components
            if component.property_type == "Measure"
        }

        units_columns = {
            col.title
            for component in self.dsd_components.qube_components
            for col in component.real_columns_used_in
            if component.property_type == "Attribute"
            and component.property
            == "http://purl.org/linked-data/sdmx/2009/attribute#unitMeasure"
        }
        self.units_column_title = units_columns.pop()

    # Function that updates dataframe to use 'Lables' values instead of 'Notation' values
    def replaceCategoricalData(self, csvw_directory: Path) -> None:

        # dimension_column_titles corresponds to individual csv files that are referenced by the main eurovision csv
        # The eurovision csv uses the 'Notation' values which are all lowercase and can contain '-'s
        # Therefore, for cleanliness, we will replace these values with the more presentable 'Label' values
        for dim in self.dimension_column_titles:
            self.data[dim] = self.data[dim].astype("category")
            dim_file = str(dim).lower() + ".csv"
            if (csvw_directory / dim_file).exists():
                replace_df = pd.read_csv(csvw_directory / dim_file)
                replace_dict = replace_df.set_index("Notation").to_dict()["Label"]
                self.data[dim] = self.data[dim].cat.rename_categories(replace_dict)

        self.data[self.measure_column_title] = self.data[
            self.measure_column_title
        ].astype("category")
        self.data[self.measure_column_title] = self.data[
            self.measure_column_title
        ].cat.rename_categories(self.measure_dict)
