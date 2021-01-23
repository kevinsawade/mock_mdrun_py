#!/usr/bin/python3

# import
import os
import sys
import glob
import shutil
import argparse

def readlastline(f):
    f.seek(-2, 2)              # Jump to the second last byte.
    while f.read(1) != b"\n":  # Until EOL is found ...
        f.seek(-2, 1)            # ... jump back, over the read byte plus one more.
    return f.read().decode('utf-8')            # Read all data from this point on.

def get_last_step_from_file(file):
    with open(file, 'rb') as f:
        lastline = readlastline(f)
    start = [int(s) for s in lastline.split() if s.isdigit()][0] + 1
    return start

def get_first_step_from_file(file):
    with open(file, 'r') as f:
        line = f.readline()
    start = [int(s) for s in line.split() if s.isdigit()][0]
    return start
    
def read_tpr(tpr_file):
    if not os.path.isfile(tpr_file):
        raise FileNotFoundError("No such file: {}".format(tpr_file))
    else:
        with open(tpr_file, 'r') as f:
            sim_length = int(f.read())
        return sim_length
    
def get_max_copy(basedir, filename):
    if basedir:
        if '/' in filename:
            filename = os.path.split(filename)[-1]
        files = glob.glob("{}/*{}*".format(basedir, filename))
    else:
        files = glob.glob("*{}*".format(filename))
    if not any(['#' in f for f in files]):
        return 0
    return max(map(lambda y: int(y.split(filename.split('.')[0])[1].split('.')[-1].rstrip('#')), filter(lambda x: True if '#' in x else False, files)))

def get_max_part(basedir, filename):
    filename, extension = filename.split('.')
    if basedir:
        files = glob.glob("{}/*{}.part*.{}*".format(basedir, filename, extension))
    else:
        files = glob.glob("*{}.part*.{}*".format(filename, extension))
    if any(['part' in f for f in files]):
        return max(map(lambda x: int(x.split('.')[-2].lstrip('part')) if not '#' in x else int(x.split('.')[-3].lstrip('part')), files))
    return 1

def decide_filename(deffnm, append):
    # get MAXBACKUP from environs
    try: max_backup = os.environ['GMX_MAXBACKUP']
    except KeyError: max_backup = 99
    
    # work with deffnm and cut it into parts
    if deffnm:
        basedir, filename = os.path.split(deffnm)
        filename += '.xtc'
        deffnm += '.xtc'
    else:
        basedir = ''
        filename = 'traj.xtc'
        deffnm = 'traj.xtc'
        
    # find and parse topol.tpr
    if deffnm == 'traj.xtc':
        topol_tpr = 'topol.tpr'
    else:
        topol_tpr = deffnm + '.tpr'
    sim_length = read_tpr(topol_tpr)
        
    # check if there
    if not os.path.isfile(deffnm) or os.path.getsize(deffnm) < 1:
        return deffnm, sim_length, 0
    elif (os.path.isfile(deffnm) and append) or (os.path.isfile(deffnm) and get_last_step_from_file(deffnm) == sim_length):
        start = get_last_step_from_file(deffnm)
        if start == sim_length:
            start = 0
            new_copy = get_max_copy(basedir, filename) + 1
            if new_copy >= max_backup:
                raise Exception("Reached max number of Backups.")
            if basedir:
                filename = "{}/#{}.{}#".format(basedir, filename, new_copy)
            else:
                filename = "#{}.{}#".format(filename, new_copy)
            shutil.move(deffnm, filename)
            print("Back Off! I backed up {} to {}".format(deffnm, filename))
        return deffnm, sim_length, start
    elif os.path.isfile(deffnm) and not append:
        part = get_max_part(basedir, filename)
        # print('part:', part)
        if part >= 9999:
            raise Exception("Reached max number of parts.")
        i, j = filename.split('.')
        if part == 1:
            start = get_last_step_from_file(deffnm)
            prev_filename = deffnm
        else:
            if basedir:
                prev_filename = "{}/{i}.part{}.{}".format(basedir, i, str(part).zfill(4), j)
                start = get_last_step_from_file(prev_filename)
            else:
                prev_filename = "{}.part{}.{}".format(i, str(part).szill(4), j)
                start = get_last_step_from_file(prev_filename)
        # print('start:', start)
        # print('prev_filename:', prev_filename)
        if start == sim_length:
            start = get_first_step_from_file(prev_filename)
            if part == 1:
                new_copy = get_max_copy(basedir, deffnm) + 1
            else:
                new_copy = get_max_copy(basedir, prev_filename) + 1
            # print('new_copy:', new_copy)
            if new_copy >= max_backup:
                raise Exception("Reached max number of Backups.")
            if basedir:
                new_copy = "{}/#{}.part{}.{}.{}#".format(basedir, i, str(part).zfill(4), j, new_copy)
            else:
                new_copy = "#{}.part{}.{}.{}#".format(i, str(part).zfill(4), j, new_copy)
            shutil.move(prev_filename, new_copy)
            print("Back Off! I backed up {} to {}".format(prev_filename, new_copy))
            return prev_filename, sim_length, start
        else:
            part = str(part + 1).zfill(4)
            if basedir:
                filename = "{}/{}.part{}.{}".format(basedir, i, part, j)
            else:
                filename = "{}.part{}.{}".format(i, part, j)
            return filename, sim_length, start
    
def run_sim(file, sim_length, max_step, start, deffnm):
    # get MAXBACKUP from environs
    try: max_backup = os.environ['GMX_MAXBACKUP']
    except KeyError: max_backup = 99
    
    # decide on start and stop
    if max_step == -1:
        stop = sim_length
    else:
        stop = max_step + start
        
    # run
    with open(file, 'a+') as f:
        for i in range(start, stop):
            if i == sim_length:
                break
            f.write("Simulation at step {}\n".format(i))
            
    # create .gro
    if stop == sim_length:
        gro_filename = file.replace('xtc', 'gro')
        if not deffnm:
            gro_filename = gro_filename.replace('traj', 'confout')
        basedir = os.path.split(gro_filename)[0]
        if os.path.isfile(gro_filename):
            new_copy = get_max_copy(basedir, gro_filename) + 1
            if new_copy >= max_backup:
                raise Exception("Reached max number of Backups.")
            if basedir:
                filename = "{}/#{}.{}#".format(basedir, gro_filename, new_copy)
            else:
                filename = "#{}.{}#".format(gro_filename, new_copy)
            shutil.move(gro_filename, filename)
            print("Back Off! I backed up {} to {}".format(gro_filename, filename))
        with open(gro_filename, 'w+') as f:
            f.write("finished mock mdrun at step {}\n".format(i))
        
def mdrun(deffnm='', append=True, max_step=-1):
    xtc_file, sim_length, start = decide_filename(deffnm, append)
    run_sim(xtc_file, sim_length, max_step, start, deffnm)

class ActionNoYes(argparse.Action):
    def __init__(self, opt_name, dest, default=True, required=False, help=None):
        super(ActionNoYes, self).__init__(['-' + opt_name, '-no' + opt_name], dest, nargs=0, const=None, default=default, required=required, help=help)
    def __call__(self, parser, namespace, values, option_string=None):
        if option_string.starts_with('-no'):
            setattr(namespace, self.dest, False)
        else:
            setattr(namespace, self.dest, True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    description=""":-)           mdrun.py mocks the behavior of gmx mdrun          (-:\n

    Want to test whether your bash scripts which automate long and iterative\n
    sims work? This is the tool to use. This script creates files similar to gmx\n
    mdrun. If -deffnm is not supplied the ASCII test file topol.tpr will be read for\n
    the number of steps to be run. traj.xtc will be filled with lines saying\n
    'At step XXX' and if the full number of steps is reached, a confout.gro will be created.\n
    If -deffnm is set, the default name will be used for .tpr, .xtc and .gro files.\n
    This tool support -[no]append and produces parts files in a similar fashion to gromacs.\n
    Using the environment variable GMX_MAXBACKUP (default 99) also the number of maximum copies\n
    will be respected. Please understand that this is a very basic script which does not support\n
    -s, -cpi options.
    """)
    parser.add_argument('-deffnm', metavar='<string>', default='', type=str, help="Set the default filename for all file options")
    parser.add_argument('-maxs', metavar='<int>', default=-1, type=int, help="Similar to gromacs -maxh, but this time terminate after this many steps")
    parser._add_action(ActionNoYes('append', 'append', help="Append or write into part files. Default noappend."))
    args = parser.parse_args([])
    mdrun(deffnm=args.deffnm, append=args.append, max_step=args.maxs)
