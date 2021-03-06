#!/usr/bin/env python
# coding: utf8
import time
import os
import sys
from optparse import OptionParser
path_of_this_script = os.path.split(os.path.realpath(__file__))[0]
sys.path.append(os.path.join(path_of_this_script, ".."))
from Library.assembly_parser import *
from Library.seq_parser import *
from Library.pipe_control_func import logging, timed_log, simple_log, set_time_limit
path_of_this_script = os.path.split(os.path.realpath(__file__))[0]
import random


def get_options(print_title):
    parser = OptionParser("disentangle_organelle_assembly.py -F plant_cp -g input.fastg -t input.tab -o output_dir")
    parser.add_option("-g", dest="fastg_file",
                      help="input fastg format file.")
    parser.add_option("-t", dest="tab_file",
                      help="input tab format file (*.csv; the postfix 'csv' was in conformity with Bandage) "
                           "produced by slim_fastg.py.")
    parser.add_option("-o", dest="output_directory",
                      help="output directory.")
    parser.add_option("-F", dest="mode",
                      help="organelle type: plant_cp/plant_mt/plant_nr/animal_mt/fungus_mt/anonym.")
    parser.add_option("--acyclic-allowed", dest="acyclic_allowed", default=False, action="store_true",
                      help="By default, this script would only disentangle the circular graph (the complete circular "
                           "organelle genome), and would directly give up linear/broken graphs). Choose this option "
                           "to try for linear/broken cases.")
    parser.add_option("--weight-f", dest="weight_factor", type=float, default=100.0,
                      help="weight factor for excluding non-target contigs. Default:%default")
    parser.add_option("--depth-f", dest="depth_factor", type=float, default=10.,
                      help="Depth factor for excluding non-target contigs. Default:%default")
    parser.add_option("--type-f", dest="type_factor", type=float, default=3.,
                      help="Type factor for identifying genome type tag. Default:%default")
    parser.add_option("--contamination-depth", dest="contamination_depth", default=3., type=float,
                      help="Depth factor for confirming contaminating contigs. Default:%default")
    parser.add_option("--contamination-similarity", dest="contamination_similarity", default=0.9, type=float,
                      help="Similarity threshold for confirming contaminating contigs. Default:%default")
    parser.add_option("--no-degenerate", dest="degenerate", default=True, action="store_false",
                      help="Disable making consensus from parallel contig based on nucleotide degenerate table.")
    parser.add_option("--degenerate-depth", dest="degenerate_depth", default=1.5, type=float,
                      help="Depth factor for confirming parallel contigs. Default:%default")
    parser.add_option("--degenerate-similarity", dest="degenerate_similarity", default=0.98, type=float,
                      help="Similarity threshold for confirming parallel contigs. Default:%default")
    parser.add_option("--expected-max-size", dest="expected_max_size", default=200000, type=int,
                      help="Expected maximum target genome size. Default: 200000 (-F plant_cp/fungus_mt), "
                           "50000 (-F plant_nr/animal_mt/fungus_mt), 600000 (-F plant_mt)")
    parser.add_option("--expected-min-size", dest="expected_min_size", default=10000, type=int,
                      help="Expected mininum target genome size. Default: %default")
    parser.add_option("--keep-all-polymorphic", dest="only_keep_max_cov", default=True, action="store_false",
                      help="By default, this script would pick the contig with highest coverage among all parallel "
                           "(polymorphic) contigs when degenerating was not applicable. "
                           "Choose this flag to export all combinations.")
    parser.add_option("--min-sigma", dest="min_sigma_factor", type=float, default=0.1,
                      help="Minimum deviation factor for excluding non-target contigs. Default:%default")
    parser.add_option("--min-depth", dest="min_cov", type=float, default=0.,
                      help="Minimum coverage for a contig to be included in disentangling. Default:%default")
    parser.add_option("--max-depth", dest="max_cov", type=float, default=inf,
                      help="Minimum coverage for a contig to be included in disentangling. Default:%default")
    parser.add_option("--prefix", dest="prefix", default="target",
                      help="Prefix of output files inside output directory. Default:%default")
    parser.add_option("--keep-temp", dest="keep_temp_graph", default=False, action="store_true",
                      help="export intermediate graph file.")
    parser.add_option("--time-limit", dest="time_limit", default=3600, type=int,
                      help="time limit for the disentangling process. Default:%default")
    parser.add_option("--random-seed", dest="random_seed", default=12345, type=int,
                      help="Random seed (only for disentangling at this moment). Default: %default")
    parser.add_option("--continue", dest="resume", default=False, action="store_true",
                      help="continue mode.")
    parser.add_option("--verbose", dest="verbose", default=False, action="store_true",
                      help="verbose logging.")
    parser.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="for debug.")
    options, argv = parser.parse_args()
    if (options.fastg_file is None) or (options.tab_file is None) or (options.output_directory is None) \
            or (options.mode is None):
        parser.print_help()
        sys.stdout.write("Insufficient arguments!\n")
        sys.exit()
    else:
        if options.output_directory and not os.path.exists(options.output_directory):
            os.mkdir(options.output_directory)
        log = simple_log(logging.getLogger(), options.output_directory, options.prefix + ".disentangle.")
        log.info(print_title)
        log.info(' '.join(sys.argv) + '\n')
        log = timed_log(log, options.output_directory, options.prefix + ".disentangle.")
        if "--expected-max-size" not in sys.argv:
            if options.mode == "plant_mt":
                options.expected_max_size *= 3
            elif options.mode in ("plant_nr", "animal_mt", "fungus_mt"):
                options.expected_max_size /= 4
        random.seed(options.random_seed)
        np.random.seed(options.random_seed)
        return options, log


def main():
    time0 = time.time()
    print_title = "\nThis is a script for extracting circular organelle genome from assembly result (fastg). " + \
                  "\nBy jinjianjun@mail.kib.ac.cn\n\n"
    options, log = get_options(print_title)

    @set_time_limit(options.time_limit)
    def disentangle_circular_assembly(fastg_file, tab_file, prefix, weight_factor, type_factor, mode="plant_cp",
                                      log_hard_cov_threshold=10., expected_max_size=inf, expected_min_size=0,
                                      contamination_depth=3., contamination_similarity=5.,
                                      degenerate=True, degenerate_depth=1.5, degenerate_similarity=1.5,
                                      min_sigma_factor=0.1, only_max_c=True, keep_temp=False, acyclic_allowed=False,
                                      verbose=False, log=None, debug=False):
        if options.resume and os.path.exists(prefix + ".graph1.selected_graph.gfa"):
            pass
            if log:
                log.info(">>> Result graph existed!")
            else:
                sys.stdout.write(">>> Result graph existed!\n")
        else:
            time_a = time.time()
            if log:
                log.info(">>> Parsing " + fastg_file + " ..")
            else:
                sys.stdout.write("Parsing " + fastg_file + " ..\n")
            input_graph = Assembly(fastg_file, min_cov=options.min_cov, max_cov=options.max_cov)
            time_b = time.time()
            if log:
                log.info(">>> Parsing input fastg file finished: " + str(round(time_b - time_a, 4)) + "s")
            else:
                sys.stdout.write("\n>>> Parsing input fastg file finished: " + str(round(time_b - time_a, 4)) + "s\n")
            temp_graph = prefix + ".temp.fastg" if keep_temp else None

            copy_results = input_graph.find_target_graph(tab_file, mode=mode, type_factor=type_factor,
                                                         weight_factor=weight_factor,
                                                         log_hard_cov_threshold=log_hard_cov_threshold,
                                                         contamination_depth=contamination_depth,
                                                         contamination_similarity=contamination_similarity,
                                                         degenerate=degenerate, degenerate_depth=degenerate_depth,
                                                         degenerate_similarity=degenerate_similarity,
                                                         expected_max_size=expected_max_size,
                                                         expected_min_size=expected_min_size,
                                                         only_keep_max_cov=only_max_c,
                                                         min_sigma_factor=min_sigma_factor,
                                                         temp_graph=temp_graph,
                                                         broken_graph_allowed=acyclic_allowed,
                                                         verbose=verbose, log_handler=log,
                                                         debug=debug)
            time_c = time.time()
            if log:
                log.info(">>> Detecting target graph finished: " + str(round(time_c - time_b, 4)) + "s")
                if len(copy_results) > 1:
                    log.info(str(len(copy_results)) + " set(s) of graph detected.")
            else:
                sys.stdout.write("\n\n>>> Detecting target graph finished: " + str(round(time_c - time_b, 4)) + "s\n")
                if len(copy_results) > 1:
                    sys.stdout.write(str(len(copy_results)) + " set(s) of graph detected.\n")

            degenerate_base_used = False
            if acyclic_allowed:
                for go_res, copy_res in enumerate(copy_results):
                    broken_graph = copy_res["graph"]
                    count_path = 0
                    for this_paths, other_tag in broken_graph.get_all_paths(mode=mode, log_handler=log):
                        count_path += 1
                        all_contig_str = []
                        for go_contig, this_p_part in enumerate(this_paths):
                            this_contig = broken_graph.export_path(this_p_part)
                            if DEGENERATE_BASES & set(this_contig.seq):
                                degenerate_base_used = True
                            all_contig_str.append(">contig_" + str(go_contig + 1) + "--" + this_contig.label + "\n" +
                                                  this_contig.seq + "\n")
                        open(prefix + ".graph" + str(go_res + 1) + other_tag + "." + str(count_path) + 
                             ".path_sequence.fasta", "w").write("\n".join(all_contig_str))
                    broken_graph.write_to_gfa(prefix + ".graph" + str(go_res + 1) + ".selected_graph.gfa")
            else:
                for go_res, copy_res in enumerate(copy_results):
                    idealized_graph = copy_res["graph"]
                    # should add making one-step-inversion pairs for paths,
                    # which would be used to identify existence of a certain isomer using mapping information
                    count_path = 0
                    for this_path, other_tag in idealized_graph.get_all_circular_paths(mode=mode, log_handler=log):
                        count_path += 1
                        this_seq_obj = idealized_graph.export_path(this_path)
                        if DEGENERATE_BASES & set(this_seq_obj.seq):
                            degenerate_base_used = True
                        open(prefix + ".graph" + str(go_res + 1) + other_tag + "." + str(count_path) + 
                             ".path_sequence.fasta", "w").write(this_seq_obj.fasta_str())
                    idealized_graph.write_to_gfa(prefix + ".graph" + str(go_res + 1) + ".selected_graph.gfa")
            if degenerate_base_used:
                log.warning("Degenerate base(s) used!")
            time_d = time.time()
            if log:
                log.info(">>> Solving and unfolding graph finished: " + str(round(time_d - time_c, 4)) + "s")
            else:
                sys.stdout.write("\n\n>>> Solving and unfolding graph finished: " + str(round(time_d - time_c, 4)) + "s\n")

    try:
        disentangle_circular_assembly(options.fastg_file, options.tab_file,
                                      os.path.join(options.output_directory, options.prefix),
                                      type_factor=options.type_factor,
                                      mode=options.mode,
                                      weight_factor=options.weight_factor,
                                      log_hard_cov_threshold=options.depth_factor,
                                      contamination_depth=options.contamination_depth,
                                      contamination_similarity=options.contamination_similarity,
                                      degenerate=options.degenerate, degenerate_depth=options.degenerate_depth,
                                      degenerate_similarity=options.degenerate_similarity,
                                      expected_max_size=options.expected_max_size,
                                      expected_min_size=options.expected_min_size,
                                      min_sigma_factor=options.min_sigma_factor,
                                      only_max_c=options.only_keep_max_cov, acyclic_allowed=options.acyclic_allowed,
                                      keep_temp=options.keep_temp_graph,
                                      log=log, verbose=options.verbose, debug=options.debug)
        log = simple_log(logging.getLogger(), options.output_directory, options.prefix + ".disentangle.")

        log.info('\nTotal cost: ' + str(round(time.time() - time0, 4)) + 's\n')
    except Exception as e:
        if options.debug:
            log.exception("")
        else:
            log.exception(str(e))
        log.exception("Disentangling failed!")
        if not options.acyclic_allowed:
            log.info("You might try again with '--acyclic-allowed' to export contig(s) instead of circular genome.")
        log = simple_log(log, options.output_directory, options.prefix + ".disentangle.")
        log.info("\nTotal cost " + str(time.time() - time0))
        log.info("Please email jinjianjun@mail.kib.ac.cn if you find bugs!\n")
    logging.shutdown()


if __name__ == '__main__':
    main()


"""Copyright 2018 Jianjun Jin"""
