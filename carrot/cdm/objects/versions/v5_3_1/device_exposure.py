import pandas as pd
from ...common import DestinationTable, DestinationField


class DeviceExposure(DestinationTable):
    """
    CDM Device Exposure object class
    """

    name = "device_exposure"

    def __init__(self, name=None):
        self.device_exposure_id = DestinationField(
            dtype="Integer", required=True, pk=True
        )
        self.person_id = DestinationField(dtype="Integer", required=True)
        self.device_concept_id = DestinationField(dtype="Integer", required=True)
        # Q: Does this "required" param reflect the same param on OMOP CDM?
        self.device_exposure_start_date = DestinationField(dtype="Date", required=False)
        self.device_exposure_start_datetime = DestinationField(
            dtype="Timestamp", required=True
        )
        self.device_exposure_end_date = DestinationField(dtype="Date", required=False)
        self.device_exposure_end_datetime = DestinationField(
            dtype="Timestamp", required=False
        )
        self.device_type_concept_id = DestinationField(dtype="Integer", required=False)
        self.quantity = DestinationField(dtype="Integer", required=False)
        self.provider_id = DestinationField(dtype="Integer", required=False)
        self.visit_occurrence_id = DestinationField(dtype="Integer", required=False)
        self.visit_detail_id = DestinationField(dtype="Integer", required=False)
        self.unique_device_id = DestinationField(dtype="Text255", required=False)
        self.production_id = DestinationField(dtype="Text255", required=False)
        self.device_source_value = DestinationField(dtype="Text50", required=False)
        self.device_source_concept_id = DestinationField(
            dtype="Integer", required=False
        )
        self.unit_concept_id = DestinationField(dtype="Integer", required=False)
        self.unit_source_value = DestinationField(dtype="Text50", required=False)
        self.unit_source_concept_id = DestinationField(dtype="Integer", required=False)

        if name is None:
            name = hex(id(self))
        super().__init__(name, self.name)

    def get_df(self, **kwargs):
        """
        Overload/append the creation of the dataframe, specifically for the device_exposure objects
        * device_concept_id  is required to be not null
          this can happen when spawning multiple rows from a person
          we just want to keep the ones that have actually been filled

        Returns:
           pandas.Dataframe: output dataframe
        """

        df = super().get_df(**kwargs)
        if self.automatically_fill_missing_columns == True:
            if df["device_exposure_start_date"].isnull().all():
                df["device_exposure_start_date"] = self.tools.get_date(
                    df["device_exposure_start_datetime"]
                )

            if df["device_exposure_end_date"].isnull().all():
                df["device_exposure_end_date"] = self.tools.get_date(
                    df["device_exposure_end_datetime"]
                )
        return df
