# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""All GGRC scoping model classes grouped together for convenience."""

from ggrc.models.access_group import AccessGroup
from ggrc.models.data_asset import DataAsset
from ggrc.models.facility import Facility
from ggrc.models.market import Market
from ggrc.models.metric import Metric
from ggrc.models.org_group import OrgGroup
from ggrc.models.product import Product
from ggrc.models.product_group import ProductGroup
from ggrc.models.project import Project
from ggrc.models.system import Process
from ggrc.models.system import System
from ggrc.models.technology_environment import TechnologyEnvironment
from ggrc.models.vendor import Vendor


SCOPING_MODELS = [
    AccessGroup,
    DataAsset,
    Facility,
    Market,
    Metric,
    OrgGroup,
    Process,
    Product,
    ProductGroup,
    Project,
    System,
    TechnologyEnvironment,
    Vendor,
]


SCOPING_MODELS_NAMES = [m.__name__ for m in SCOPING_MODELS]
