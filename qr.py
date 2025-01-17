"""This is the entry point into Q|R. It takes user inputs,
   and then constructs all of the objects
   needed to carry out the quantum refinement.

   - fmodel (crystallographic information)
  - calculator (composite object)
  - restraints_manager (computes energy and gradients using either qm codes or
    cctbx (standard))
  - geometry_restraints_manager (analyses geometry e.g. bond RMSDs)
  - weights (scale factors needed to scale up or down data versus restraints
    contributions)
  Then we process them by the refinement/optimization engine, driver.py:

   driver.refine(params   = params,
               fmodel     = fmodel,
               calculator = calculator_manager,
               results    = results)
   results_manager (store all reportable information, and write it out as a log,
   and also write our final pdb structure.)
   """
from __future__ import division

import os
import sys
import time
import pickle
import mmtbx.command_line
import mmtbx.f_model
import mmtbx.utils
from libtbx.utils import Sorry
from libtbx import easy_pickle
from libtbx import group_args
from libtbx.utils import null_out
from mmtbx import monomer_library
import mmtbx.monomer_library.pdb_interpretation
import mmtbx.restraints
from fragment import fragments
import calculator
import driver
import restraints
import cluster_restraints
import results
from qrefine.super_cell import expand
import mmtbx.model.statistics
from libtbx import Auto
from ase.io import read as ase_io_read

master_params_str ="""

max_atoms = 15000
  .type = int
  .help = maximum number of atoms
debug = False
    .type = bool
    .help = flag to control verbosity of output for debugging problematic code.
cluster{
  charge_cutoff = 8.0
    .type = float
    .help = distance for point charge cutoff
  clustering = False
    .type = bool
    .help = enable/disable clustering
  charge_embedding = False
    .type = bool
    .help = point charge embedding
  two_buffers = False
    .type = bool
    .help = two-buffers are used when gradients for the whole system do not match the joined gradients from fragments \
            when only as single buffer was used to surround each clusters.
  maxnum_residues_in_cluster = 15
    .type = int
    .help = maximum number of residues in a cluster
  clustering_method = gnc  *bcc
    .type = choice(multi=False)
    .help = type of clustering algorithm
  altloc_method = *average subtract
    .type = choice(multi=False)
    .help = two strategies on how to join energies from multiple energy and gradient calculations are performed for alternate locations.
  g_scan  = 10 15 20
    .type = str
    .help = sequence of numbers specifying maxnum_residues_in_cluster for gradient convergence test (mode=gtest), treat as string!
  g_mode = None
    .type = int
    .help = manual control over gradient test loops (1=standard, 2=standard + point-charges, 3=two buffer 4=two_buffer+ point-charges)
  save_clusters = True
    .type = bool
    .help = save currently used fragments and clusters to disk as PDBs.
}

restraints = cctbx *qm
  .type = choice(multi=False)
quantum {
  engine_name = *mopac ani torchani terachem turbomole pyscf orca gaussian xtb
    .type = choice(multi=False)
    .help = choose the QM program
  charge= None
    .type = int
    .help = The formal charge of the entire molecule
  basis = Auto
    .type = str
    .help = pre-defined defaults
  method = Auto
    .type = str
    .help = Defaults to HF for all but MOPAC (PM7), xTB (GFN2) and TorchANI (ani-1x_8x)
  memory = None
    .type = str
    .help = memory for the QM program
  nproc = None
    .type = int
    .help = number of parallel processes for the QM program
  qm_addon = gcp dftd3 gcp-d3
    .type = choice(multi=False)
    .help = allows additional calculations of the gCP and/or DFT-D3 corrections using their stand-alone programs
  qm_addon_method = None
    .type = str
    .help = specifies flags for the qm_addon. See manual for details.
}

refine {
  dry_run=False
    .type = bool
    .help = do not perform calculations, only setup steps
  sf_algorithm = *direct fft
    .type = choice(multi=False)
    .help = algorithm used to compute structure factors, either the direct method or fast fourier transform.
  refinement_target_name = *ml ls_wunit_k1
    .type = choice
  mode = opt *refine gtest
    .type = choice(multi=False)
    .help = choose between refinement, geometry optimization or gradient test
  number_of_macro_cycles=1
    .type = int
    .help = number of macro cycles used in the refinement procedure.
  number_of_weight_search_cycles=50
    .type = int
  number_of_refine_cycles=5
    .type = int
    .help = maximum number of refinement cycles
  number_of_micro_cycles=50
    .type = int
    .help = maximum number of micro cycles used in refinement
  data_weight=None
    .type = float
  choose_best_use_r_work = False
    .type = bool
  skip_weight_search = False
    .type = bool
  adjust_restraints_weight_scale_value = 2
    .type = float
  max_iterations_weight = 50
    .type = int
  max_iterations_refine = 50
    .type = int
  use_ase_lbfgs = False
    .type = bool
    .help = used for debugging the lbfgs minimizer from cctbx.
  line_search = True
    .type = bool
    .help = flag to use a line search in minimizer.
  stpmax = 3
    .type = float
    .help = maximum step length, empirically we find 3 for cctbx, but 0.2 is better for QM methods.
  gradient_only = False
    .type = bool
    .help = use the gradient only line search according to JA Snyman 2005.
  update_all_scales = True
    .type = bool
  refine_sites = True
    .type = bool
    .help = only refine the cartesian coordinates of the molecular system.
  refine_adp = False
    .type = bool
    .help = adp refinement are not currently supported. 
  restraints_weight_scale = 1.0
    .type = float
  shake_sites = False
    .type = bool
  use_convergence_test = True
    .type = bool
  max_bond_rmsd = 0.03
    .type = float
  max_r_work_r_free_gap = 5.0
    .type = float
  r_tolerance = 0.001
    .type = float
  rmsd_tolerance = 0.01
    .type = float
    .help = maximum acceptable tolerance for the rmsd. 
  opt_log = False
    .type = bool
    .help = additional output of the L-BFGS optimizer
  pre_opt = False
    .type = bool
    .help = pre-optimization using steepest decent (SD) and conjugate gradient (CG) techniques w/o line search
  pre_opt_stpmax = 0.1
    .type = float
    .help = step size
  pre_opt_iter= 10
    .type = int
    .help = max. iterations for pre-optimizer
  pre_opt_switch = 2
    .type = int
    .help = max. iterations before switching from SD to CG
  pre_opt_gconv = 3000
    .type = float
    .help = gradient norm convergence threshold for pre-optimizer
}

parallel {
  method = *multiprocessing slurm pbs sge lsf threading
    .type = choice(multi=False)
    .help = type of parallel mode and efficient method of processes on the \
            current computer. The others are queueing protocols with the \
            expection of threading which is not a safe choice.
  nproc = None
    .type = int
    .help = Number of processes to use
  qsub_command = None
    .type = str
    .help = Specific command to use on the queue system
}

output_file_name_prefix = None
  .type = str
output_folder_name = "pdb"
  .type = str
shared_disk = True
  .type = bool
  .help = this is deprecated no because we now only use the parallel map.
rst_file = None
  .type = str
  .help = Restart file to use for determining location in run. Loads previous \
          results of weight calculations.
dump_gradients=None
  .type = str
  .help = used for debugging gradients when clustering.
"""

def get_master_phil():
  return mmtbx.command_line.generate_master_phil_with_inputs(
    phil_string=master_params_str)

def show_cc(map_data, xray_structure, log):
  import mmtbx.maps.mtriage
  from mmtbx.maps.correlation import five_cc
  xrs = xray_structure
  xrs.scattering_type_registry(table="electron")
  mtriage = mmtbx.maps.mtriage.mtriage(
    map_data         = map_data,
    crystal_symmetry = xrs.crystal_symmetry())
  d99 = mtriage.get_results().masked.d99
  print >> log, "Resolution of map is: %6.4f" %d99
  result = five_cc(
    map              = map_data,
    xray_structure   = xrs,
    d_min            = d99,
    compute_cc_box   = True).result
  print >> log, "Map-model correlation coefficient (CC)"
  print >> log, "  CC_mask  : %6.4f" %result.cc_mask
  print >> log, "  CC_volume: %6.4f" %result.cc_volume
  print >> log, "  CC_peaks : %6.4f" %result.cc_peaks
  print >> log, "  CC_box   : %6.4f" %result.cc_box


def create_fmodel(cmdline, log):
  fmodel = mmtbx.f_model.manager(
    f_obs          = cmdline.f_obs,
    r_free_flags   = cmdline.r_free_flags,
    xray_structure = cmdline.xray_structure,
    target_name    = cmdline.params.refine.refinement_target_name)
  if(cmdline.params.refine.update_all_scales):
    fmodel.update_all_scales(remove_outliers=False)
    fmodel.show(show_header=False, show_approx=False)
  print >> log, "Initial r_work=%6.4f r_free=%6.4f" % (fmodel.r_work(), fmodel.r_free())
  log.flush()
  return fmodel

def process_model_file(pdb_file_name, cif_objects, crystal_symmetry):
  import iotbx.pdb
  params = mmtbx.model.manager.get_default_pdb_interpretation_params()
  params.pdb_interpretation.use_neutron_distances = True
  params.pdb_interpretation.restraints_library.cdl = False
  params.pdb_interpretation.sort_atoms = False
  pdb_inp = iotbx.pdb.input(file_name=pdb_file_name)
  model = mmtbx.model.manager(
    model_input               = pdb_inp,
    crystal_symmetry          = crystal_symmetry,
    restraint_objects         = cif_objects,
    process_input             = True,
    pdb_interpretation_params = params,
    log                       = null_out())
  model.setup_restraints_manager(grm_normalization=False)
  return group_args(
    model              = model,
    pdb_hierarchy      = model.get_hierarchy(),
    xray_structure     = model.get_xray_structure(),
    cif_objects        = cif_objects,
    ase_atoms          = ase_io_read(pdb_file_name) # To be able to use ASE LBFGS
    )

def create_fragment_manager(
      cif_objects,
      pdb_hierarchy,
      crystal_symmetry,
      params,
      file_name      = os.path.join("ase","tmp_ase.pdb")):
  if(not params.cluster.clustering): return None
  return fragments(
    cif_objects                = cif_objects,
    working_folder             = os.path.split(file_name)[0]+ "/",
    clustering_method          = params.cluster.clustering_method,
    altloc_method              = params.cluster.altloc_method,
    maxnum_residues_in_cluster = params.cluster.maxnum_residues_in_cluster,
    charge_embedding           = params.cluster.charge_embedding,
    two_buffers                = params.cluster.two_buffers,
    pdb_hierarchy              = pdb_hierarchy,
    qm_engine_name             = params.quantum.engine_name,
    crystal_symmetry           = crystal_symmetry,
    debug                      = params.debug,
    charge_cutoff              = params.cluster.charge_cutoff,
    save_clusters              = params.cluster.save_clusters)

def create_restraints_manager(
      params,
      model,
      fragment_manager=None):
  if(params.restraints == "cctbx"):
    restraints_manager = restraints.from_cctbx(
      restraints_manager = model.model.get_restraints_manager())
  else:
    assert params.restraints == "qm"
    restraints_manager = restraints.from_qm(
      cif_objects                = model.cif_objects,
      method                     = params.quantum.method,
      basis                      = params.quantum.basis,
      pdb_hierarchy              = model.pdb_hierarchy,
      charge                     = params.quantum.charge,
      qm_engine_name             = params.quantum.engine_name,
      qm_addon                   = params.quantum.qm_addon,
      qm_addon_method            = params.quantum.qm_addon_method,
      memory                     = params.quantum.memory,
      nproc                      = params.quantum.nproc,
      crystal_symmetry           = model.xray_structure.crystal_symmetry(),
      clustering                 = params.cluster.clustering)
  return restraints_manager

def create_calculator(weights, params, restraints_manager, fmodel=None,
                      model=None):
  if(weights is None):
    weights = calculator.weights(
      shake_sites             = params.refine.shake_sites ,
      restraints_weight       = 1.0,
      data_weight             = params.refine.data_weight,
      restraints_weight_scale = params.refine.restraints_weight_scale)
  if(params.refine.refine_sites):
    if(params.refine.mode == "refine"):
      return calculator.sites(
        fmodel             = fmodel,
        restraints_manager = restraints_manager,
        weights            = weights,
        dump_gradients     = params.dump_gradients,
        ase_atoms          = model.ase_atoms)
    else:
      return calculator.sites_opt(
        restraints_manager = restraints_manager,
        xray_structure     = model.xray_structure,
        dump_gradients     = params.dump_gradients,
        ase_atoms          = model.ase_atoms)
  if(params.refine.refine_adp):
    return calculator.adp(
      fmodel             = fmodel,
      restraints_manager = restraints_manager,
      weights            = weights)

def validate(model, fmodel, params, rst_file, prefix, log):
  # set defaults
  outl = ''
  if params.quantum.engine_name=='mopac':
    if params.quantum.method==Auto:
      params.quantum.method='PM7'
      outl += '  Setting QM method to PM7\n'
    if params.quantum.basis==Auto:
      params.quantum.basis=''
  if params.quantum.engine_name=='xtb':
    if params.quantum.method==Auto:
      params.quantum.method=' --gfn 2 --etemp 500 --acc 0.1 --gbsa h2o'
      print >> log, '  Default method for xtb is %s' % (
          params.quantum.method,
          )
      params.quantum.basis = ''
  else:
    if params.quantum.method==Auto:
      params.quantum.method='HF'
      outl += '  Setting QM method to HF\n'
    if params.quantum.basis==Auto:
      params.quantum.basis='6-31g'
      outl += '  Setting QM basis to 6-31g\n'
  if outl:
    print >> log, '\nSetting QM defaults'
    print >> log, outl

  if params.quantum.engine_name=='mopac':
    if params.quantum.basis:
      print >> log, '  Because engine is %s basis set %s ignored' % (
        params.quantum.engine_name,
        params.quantum.basis,
        )
      params.quantum.basis = ''
    if params.quantum.method=='hf': # default
      print >> log, '  Default method set as PM7'
      params.quantum.method='PM7'


def run(model, fmodel, map_data, params, rst_file, prefix, log):
  validate(model, fmodel, params, rst_file, prefix, log)
  if(params.cluster.clustering):
    params.refine.gradient_only = True
    print >> log, " params.gradient_only", params.refine.gradient_only
  # RESTART
  if(os.path.isfile(str(rst_file))):
    print >> log, "restart info is loaded from %s" % params.rst_file
    rst_data = easy_pickle.load(params.rst_file)
    fmodel = rst_data["fmodel"]
    results_manager = rst_data["results"]
    results_manager.log = log
    weights = rst_data["weights"]
    geometry_rmsd_manager = rst_data["geometry_rmsd_manager"]
    start_fmodel = rst_data["rst_fmodel"]
    start_ph = model.pdb_hierarchy.deep_copy().adopt_xray_structure(
      start_fmodel.xray_structure)
  else:
    weights = None
    if (model.pdb_hierarchy.atoms().size() > params.max_atoms):
      raise Sorry("Too many atoms.")
    geometry_rmsd_manager =  model.model.get_restraints_manager()
    cctbx_rm_bonds_rmsd = calculator.get_bonds_rmsd(
      restraints_manager = geometry_rmsd_manager.geometry,
      xrs                = model.xray_structure)
    #
    if(params.refine.dry_run): return
    #
    r_work, r_free = None, None
    if(fmodel is not None):
      r_work, r_free = fmodel.r_work(), fmodel.r_free()
    results_manager = results.manager(
      r_work                  = r_work,
      r_free                  = r_free,
      b                       = cctbx_rm_bonds_rmsd,
      xrs                     = model.xray_structure,
      max_bond_rmsd           = params.refine.max_bond_rmsd,
      max_r_work_r_free_gap   = params.refine.max_r_work_r_free_gap,
      pdb_hierarchy           = model.pdb_hierarchy,
      mode                    = params.refine.mode,
      log                     = log,
      restraints_weight_scale = params.refine.restraints_weight_scale)
    if(params.rst_file is None):
      if(params.output_file_name_prefix is None):
        params.output_file_name_prefix = prefix
      if(os.path.exists(params.output_folder_name) is False):
        os.mkdir(params.output_folder_name)
      params.rst_file = os.path.abspath(params.output_folder_name + "/" + \
        params.output_file_name_prefix + ".rst.pickle")
    if os.path.isfile(params.rst_file):
      os.remove(params.rst_file)
    print >> log, "\n***********************************************************"
    print >> log, "restart info will be stored in %s" % params.rst_file
    print >> log, "***********************************************************\n"
    start_fmodel = fmodel
    start_ph = None # is it used anywhere? I don't see where it is used!
  if not params.refine.mode=='gtest':    
    fragment_manager = create_fragment_manager(
        params           = params,
        pdb_hierarchy    = model.pdb_hierarchy,
        cif_objects      = model.cif_objects,
        crystal_symmetry = model.xray_structure.crystal_symmetry())
    restraints_manager = create_restraints_manager(
      params           = params,
      model            = model)

  if(params.refine.mode == "gtest"):
    # needs to be moved! Perhaps also to driver
    import numpy as np
    from fragment import fragment_extracts, write_cluster_and_fragments_pdbs
    from utils.mathbox import get_grad_mad, get_grad_angle

    # determine what kind of buffer to calculate
    g_mode=[]
    if params.cluster.g_mode is None:
      g_mode.append(1)
      if params.cluster.charge_embedding:
        g_mode.append(2)
      if params.cluster.two_buffers:
        g_mode.append(3)
      if params.cluster.two_buffers and params.cluster.charge_embedding:
        g_mode.append(4)
    else:
      g_mode.append(params.cluster.g_mode)


    # reset flags
    params.cluster.clustering=True
    params.cluster.save_clusters=True
    params.cluster.charge_embedding=False
    params.cluster.two_buffers=False
    grad=[]
    idx=0
    idl=[]

    # input for cluster size
    cluster_scan=sorted([int(x) for x in params.cluster.g_scan.split()])
    # cluster_scan=[2,10]

    if g_mode[0]==0:
      params.cluster.clustering=False
      cluster_scan=[0]
      clusters=[]

    n_grad=len(cluster_scan)*len(g_mode)
    print >> log, 'Calculating %3i gradients \n' % (n_grad)
    print >> log, 'Starting loop over different fragment sizes'
    for ig in g_mode:

      print >> log,'loop for g_mode = %i ' % (ig)
      if ig == 2:
        print >> log, 'pc on'
        params.cluster.charge_embedding=True
      if ig == 3:
        print >> log, 'two_buffers on, pc off'
        params.cluster.charge_embedding=False
        params.cluster.two_buffers=True
      if ig == 4:
        print >> log, 'two_buffers on, pc on'
        params.cluster.charge_embedding=True
        params.cluster.two_buffers=True

      for max_cluster in cluster_scan:
        idl.append([ig,max_cluster])
        print >> log, 'g_mode: %s' % (" - ".join(map(str,idl[idx])))
        t0 = time.time()
        print >> log, "~max cluster size ",max_cluster
        params.cluster.maxnum_residues_in_cluster=max_cluster
        fragment_manager = create_fragment_manager(
            params           = params,
            pdb_hierarchy    = model.pdb_hierarchy,
            cif_objects      = model.cif_objects,
            crystal_symmetry = model.xray_structure.crystal_symmetry())
        restraints_manager = create_restraints_manager(
            params           = params,
            model            = model)
        if(fragment_manager is not None):
          cluster_restraints_manager = cluster_restraints.from_cluster(
            restraints_manager = restraints_manager,
            fragment_manager   = fragment_manager,
            parallel_params    = params.parallel)
        rm = restraints_manager
        if(fragment_manager is not None):
          rm = cluster_restraints_manager
          print "time taken for fragments",(time.time() - t0)
          frags=fragment_manager
          print >> log, '~  # clusters  : ',len(frags.clusters)
          print >> log, '~  list of atoms per cluster:'
          print >> log, '~   ',[len(x) for x in frags.cluster_atoms]
          print >> log, '~  list of atoms per fragment:'
          print >> log, '~   ',[len(x) for x in frags.fragment_super_atoms]

          # save fragment data. below works
          # better way is to make a single PDB file with chain IDs
          label="-".join(map(str,idl[idx]))
          write_cluster_and_fragments_pdbs(fragment_extracts=fragment_extracts(frags),directory=label)
          # cwd = os.getcwd()
          # frag_dir = os.path.join(os.getcwd(),label)
          # if not os.path.exists(frag_dir):
          #   os.mkdir(frag_dir)
          # os.chdir(frag_dir)
          # for index, selection_fragment in enumerate(frags.fragment_selections):

          #   cluster_selection = frags.cluster_selections[index]
          #   frag_selection = frags.fragment_super_selections[index]
          #   icluster = frags.pdb_hierarchy.select(cluster_selection)
          #   ifrag = frags.pdb_hierarchy_super.select(frag_selection)
          #   fn_cluster = "%s_%s_cluster.pdb" %(label,index)
          #   fn_frag = "%s_%s_frag.pdb" %(label,index)
          #   icluster.write_pdb_file(
          #     file_name        = fn_cluster,
          #     crystal_symmetry = frags.expansion.cs_box)
          #   ifrag.write_pdb_file(
          #     file_name        = fn_frag,
          #     crystal_symmetry = frags.expansion.cs_box)
          # os.chdir(cwd)

        calculator_manager = create_calculator(
          weights            = weights,
          fmodel             = start_fmodel,
          model              = model,
          params             = params,
          restraints_manager = rm)
        grad=driver.run_gradient(calculator=calculator_manager)
        print >> log, '~   gnorm',np.linalg.norm(grad)
        print >> log, '~   max_g', max(abs(i) for i in grad), ' min_g',min(abs(i) for i in grad)
        name="-".join(map(str,idl[idx]))
        np.save(name,grad)
        idx+=1
        print >> log, "total time for gradient",(time.time() - t0),'\n\n'

    print >> log, 'ready to run qr.granalyse!'

  else:
    rm = restraints_manager
    if(fragment_manager is not None):
      cluster_restraints_manager = cluster_restraints.from_cluster(
        restraints_manager = restraints_manager,
        fragment_manager   = fragment_manager,
        parallel_params    = params.parallel)
      rm = cluster_restraints_manager

    if(map_data is not None and params.refine.mode == "refine"):
      model.model.geometry_statistics(use_hydrogens=False).show()
      show_cc(
        map_data        = map_data,
        xray_structure  = model.xray_structure,
        log             = log)
      O = calculator.sites_real_space(
        model                 = model.model,
        geometry_rmsd_manager = geometry_rmsd_manager,
        max_bond_rmsd         = params.refine.max_bond_rmsd,
        map_data              = map_data,
        data_weight           = params.refine.data_weight,
        refine_cycles         = params.refine.number_of_refine_cycles,
        skip_weight_search    = params.refine.skip_weight_search,
        stpmax                = params.refine.stpmax,
        gradient_only         = params.refine.gradient_only,
        line_search           = params.refine.line_search,
        restraints_manager    = rm,
        max_iterations        = params.refine.max_iterations_refine,
        log                   = log)
      model = O.run()
      of = open("real_space_refined.pdb", "w")
      print >> of, model.model_as_pdb(output_cs=True)
      of.close()
      model.geometry_statistics(use_hydrogens=False).show()
      show_cc(
        map_data=map_data,
        xray_structure=model.get_xray_structure(),
        log=log)
      return
    else:
      calculator_manager = create_calculator(
        weights=weights,
        fmodel=start_fmodel,
        model=model,
        params=params,
        restraints_manager=rm)
      if(params.refine.mode == "refine"):
        driver.refine(
          params                = params,
          fmodel                = fmodel,
          geometry_rmsd_manager = geometry_rmsd_manager,
          calculator            = calculator_manager,
          results               = results_manager)
      else:
        driver.opt(
          params                = params,
          xray_structure        = model.xray_structure,
          geometry_rmsd_manager = geometry_rmsd_manager,
          calculator            = calculator_manager,
          results               = results_manager)
      xrs_best = results_manager.finalize(
        input_file_name_prefix  = prefix,
        output_file_name_prefix = params.output_file_name_prefix,
        output_folder_name      = params.output_folder_name,
        use_r_work              = params.refine.choose_best_use_r_work)

if (__name__ == "__main__"):
  t0 = time.time()
  log = sys.stdout
  args = sys.argv[1:]
  print >> log, '_'*80
  print >> log, 'Command line arguments'
  outl = '  '
  for arg in args:
    outl += '"%s"' % arg
  print >> log, '%s\n' % outl
  print >> log, '_'*80
  cmdline = mmtbx.command_line.load_model_and_data(
      args          = args,
      master_phil   = get_master_phil(),
      create_fmodel = False,
      out           = log)
  run(cmdline=cmdline, log = log)
  print >> log, "Time: %6.4f"%(time.time()-t0)
