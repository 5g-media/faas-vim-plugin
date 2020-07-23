# Copyright 2017 – 2020 IBM Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
No operation action responsible to persist its parameters in its activation record.

It is called by the FaaS VIM plug-in of OSM to persist needed parameters for an event-based VNF.

One of the parameters is the full ro name which is used to correlate the pod by `refresh_vms_status` plug-in hook

"""

def main(args):
    return args
