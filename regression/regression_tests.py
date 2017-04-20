from __future__ import division

import os
import time
import libtbx.load_env
from libtbx import easy_run

qrefine = libtbx.env.find_in_repositories("qrefine")
qr_reg_tests = os.path.join(qrefine, "regression")
qr_reg_data = os.path.join(qrefine, "regression/datasets")

pdb_path= os.path.join(qr_reg_data,"p1")
cluster_path = os.path.join(qr_reg_data,"cluster")
clusters_path = os.path.join(qr_reg_data,"clusters")
capping_path = os.path.join(qr_reg_data,"capping")
charmm_path = os.path.join(qr_reg_data,"charmm")

def datasets():
  return [pdb_path,
          cluster_path,
          clusters_path,
          capping_path,
          charmm_path]

def run():
  regression_tests = [
    #"test_reg_00_charge.py",
    #"test_reg_01_finalise.py",
    #"test_reg_02_finalise.py",
    #"test_reg_03_finalise.py",
    "test_reg_04_cluster.py",
  ]

  for regression_test in regression_tests:
      for dataset in datasets():
        print "Running: {} ".format(regression_test)
        print "Dataset: {} ".format(dataset)
        easy_run.call("cctbx.python %s %s"%(os.path.join(qr_reg_tests,regression_test),dataset))

if(__name__ == "__main__"):
  t0 = time.time()
  # TODO: regression can be run on an external dataset, pass in arg for filepath.
  run()
  print "Total time (all regression): %6.2f"%(time.time()-t0)
  print "OK"