#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import argparse

from pipeline.backend.pipeline import PipeLine
from pipeline.component import DataTransform
from pipeline.component import HeteroPearson
from pipeline.component import HeteroFeatureBinning
from pipeline.component import HeteroFeatureSelection
from pipeline.component import Intersection
from pipeline.component import Reader
from pipeline.interface import Data
from pipeline.interface import Model

from pipeline.utils.tools import load_job_config


def main(config="../../config.yaml", namespace=""):
    # obtain config
    if isinstance(config, str):
        config = load_job_config(config)
    parties = config.parties
    guest = parties.guest[0]
    host = parties.host[0]

    guest_train_data = {"name": "breast_hetero_guest", "namespace": f"experiment{namespace}"}
    host_train_data = {"name": "breast_hetero_host", "namespace": f"experiment{namespace}"}

    pipeline = PipeLine().set_initiator(role='guest', party_id=guest).set_roles(guest=guest, host=host)

    reader_0 = Reader(name="reader_0")
    reader_0.get_party_instance(role='guest', party_id=guest).component_param(table=guest_train_data)
    reader_0.get_party_instance(role='host', party_id=host).component_param(table=host_train_data)

    data_transform_0 = DataTransform(name="data_transform_0")
    data_transform_0.get_party_instance(role='guest', party_id=guest).component_param(with_label=True)
    data_transform_0.get_party_instance(role='host', party_id=host).component_param(with_label=False)

    intersection_0 = Intersection(name="intersection_0")

    hetero_pearson_0 = HeteroPearson(name='hetero_pearson_0', column_indexes=-1)
    hetero_binning_0 = HeteroFeatureBinning(name='hetero_binning_0')
    selection_param = {
        "name": "hetero_feature_selection_0",
        "select_col_indexes": -1,
        "select_names": [],
        "filter_methods": [
            "vif_filter",
            "correlation_filter"
        ],
        "vif_param": {
            "threshold": 5
        },
        "correlation_param": {
            "threshold": 0.5,
            "select_federated": False
        }
    }
    hetero_feature_selection_0 = HeteroFeatureSelection(**selection_param)
    pipeline.add_component(reader_0)
    pipeline.add_component(data_transform_0, data=Data(data=reader_0.output.data))
    pipeline.add_component(intersection_0, data=Data(data=data_transform_0.output.data))
    pipeline.add_component(hetero_binning_0, data=Data(data=intersection_0.output.data))
    pipeline.add_component(hetero_pearson_0, data=Data(data=intersection_0.output.data))
    pipeline.add_component(hetero_feature_selection_0, data=Data(data=intersection_0.output.data),
                           model=Model(isometric_model=[hetero_pearson_0.output.model,
                                                        hetero_binning_0.output.model]))

    pipeline.compile()

    pipeline.fit()
    # predict
    # deploy required components
    pipeline.deploy_component([data_transform_0, intersection_0,
                               hetero_binning_0, hetero_feature_selection_0])

    predict_pipeline = PipeLine()
    # add data reader onto predict pipeline
    predict_pipeline.add_component(reader_0)
    # add selected components from train pipeline onto predict pipeline
    # specify data source
    predict_pipeline.add_component(pipeline,
                                   data=Data(predict_input={pipeline.data_transform_0.input.data: reader_0.output.data}))
    # run predict model
    predict_pipeline.predict()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("PIPELINE DEMO")
    parser.add_argument("-config", type=str,
                        help="config file")
    args = parser.parse_args()
    if args.config is not None:
        main(args.config)
    else:
        main()
