"""
Insert description of .py file.
"""


def transform_ref_code(args, code_fov_pairs = None, mode = 'all'):
    r"""Description of the function here. 
    Args:
        args (dict): configuration options.
        code_fov_pairs (list): A list of tuples, where each tuple is a (code, fov) pair. Default: ``None``
        mode (str): running mode. Default: ``'all'``
    """

    import h5py
    from exm.io.io import nd2ToVol
    if not code_fov_pairs:
        code_fov_pairs = [[args.ref_code,fov] for fov in args.fovs]
    
    for code,fov in code_fov_pairs:
        print('code = {}, fov={}'.format(code,fov))
        with h5py.File(args.h5_path.format(code,fov), 'a') as f:
            for channel_name_ind, channel_name in enumerate(args.channel_names):
                if mode == '405' and '405' not in channel_name:
                    continue
                if mode == 'four' and '405' in channel_name:
                    continue
                if channel_name in f.keys():
                    continue
                fix_vol = nd2ToVol(args.nd2_path.format(code,channel_name,channel_name_ind), fov, channel_name)
                f.create_dataset(channel_name, fix_vol.shape, dtype=fix_vol.dtype, data = fix_vol)


def identify_matching_z(args,code_fov_pairs = None):

    from exm.io.io import nd2ToSlice
    import numpy as np
    import matplotlib.pyplot as plt
    import os

    if not code_fov_pairs:
        code_fov_pairs = [[code,fov] for code in args.codes if code!= args.ref_code for fov in args.fovs]
    
    for code, fov in code_fov_pairs: 

        if not os.path.exists('/mp/nas2/ruihan/ExSeqProcessing2/output/step1_matching_z/code{}/'.format(code)):
            os.makedirs('/mp/nas2/ruihan/ExSeqProcessing2/output/step1_matching_z/code{}/'.format(code))
            
        fig,axs = plt.subplots(2,5,figsize = (25,10))
            
        for i,z in enumerate(np.linspace(0,200,5)):
                
            im = nd2ToSlice(args.nd2_path.format(args.ref_code, '405', 4),fov, int(z), '405 SD')

            axs[0,i].imshow(im,vmax = 600)
            axs[0,i].set_xlabel(z)

        for i,z in enumerate(np.linspace(0,200,5)):
                
            im = nd2ToSlice(args.nd2_path.format(code, '405', 4),fov, int(z), '405 SD')
                
            axs[1,i].imshow(im,vmax = 600)
            axs[1,i].set_xlabel(z)

        plt.title('fov{} code{}'.format(fov,code))
        plt.savefig('/mp/nas2/ruihan/ExSeqProcessing2/output/step1_matching_z/code{}/fov{}.jpg'.format(code,fov))
        plt.close()


def align_truncated(args, code_fov_pairs):

    import SimpleITK as sitk
    import h5py
    from exm.io.io import nd2ToChunk

    sitk.ProcessObject_SetGlobalWarningDisplay(False)
    
    for code,fov in code_fov_pairs:

        if tuple([code,fov]) not in args.starting:
            continue
        print(code,fov)

        # Get the indexes in the matching slices in two dataset
        fix_start,mov_start,last = args.starting[tuple([code,fov])]

        # fix volume
        fix_vol = nd2ToChunk(args.nd2_path.format(args.ref_code,'405',4), fov, fix_start, fix_start+last)

        # mov volume
        mov_vol = nd2ToChunk(args.nd2_path.format(code,'405',4), fov, mov_start, mov_start+last)

        # Align
        elastixImageFilter = sitk.ElastixImageFilter()

        fix_vol_sitk = sitk.GetImageFromArray(fix_vol)
        fix_vol_sitk.SetSpacing([1.625,1.625,4.0])
        elastixImageFilter.SetFixedImage(fix_vol_sitk)

        mov_vol_sitk = sitk.GetImageFromArray(mov_vol)
        mov_vol_sitk.SetSpacing([1.625,1.625,4.0])
        elastixImageFilter.SetMovingImage(mov_vol_sitk)

        parameter_map = sitk.GetDefaultParameterMap('rigid')
        parameter_map['NumberOfSamplesForExactGradient'] = ['1000']  # NumberOfSamplesForExactGradient
        parameter_map['MaximumNumberOfIterations'] = ['15000'] # MaximumNumberOfIterations
        parameter_map['MaximumNumberOfSamplingAttempts'] = ['100'] # MaximumNumberOfSamplingAttempts
        parameter_map['FinalBSplineInterpolationOrder'] = ['1'] #FinalBSplineInterpolationOrder
        parameter_map['NumberOfResolutions'] = ['2']
        elastixImageFilter.SetParameterMap(parameter_map)
        elastixImageFilter.LogToConsoleOff()
        elastixImageFilter.Execute()

        transform_map = elastixImageFilter.GetTransformParameterMap()
        sitk.PrintParameterMap(transform_map)
        sitk.WriteParameterFile(transform_map[0], args.tform_path.format(code,fov))


        # Apply transform
        transform_map = sitk.ReadParameterFile(args.tform_path.format(code,fov))
        transformix = sitk.TransformixImageFilter()
        transformix.LogToConsoleOff()
        transformix.SetTransformParameterMap(transform_map)

        # Just visualize the first 100 slices
        mov_vol_sitk = mov_vol_sitk[:,:,:100]

        transformix.SetMovingImage(mov_vol_sitk)
        transformix.Execute()
        out = sitk.GetArrayFromImage(transformix.GetResultImage())
        
        # Save the results
        with h5py.File(args.h5_path_cropped.format(code,fov), 'w') as f:
            f.create_dataset('405', out.shape, dtype=out.dtype, data = out)


def inspect_align_truncated(args,fov_code_pairs):

    import matplotlib.pyplot as plt
    import numpy as np
    import h5py
    from exm.io.io import nd2ToSlice

    for fov,code in fov_code_pairs:
    
        if not tuple([code,fov]) in args.starting:
            continue
        print(fov,code)

        fix_start,mov_start,last = args.starting[tuple([code,fov])]
        z_stacks = np.linspace(fix_start,fix_start+last,5)

        # ---------- Full resolution -----------------
        fig,axs = plt.subplots(2,5,figsize = (20,5))
        
        for i,z in enumerate(z_stacks):
            im = nd2ToSlice(args.nd2_path.format(args.ref_code, 4,'405'),fov, int(z), '405 SD')
            axs[0,i].imshow(im,vmax = 600)
            axs[0,i].set_xlabel(z)
            axs[0,i].set_ylabel('fix')

        for i,z in enumerate(z_stacks):
            with h5py.File(args.h5_path_cropped.format(code,fov), "r") as f:
                im = f['405'][int(z),:,:]
                im = np.squeeze(im)
            axs[1,i].imshow(im,vmax = 600)
            axs[1,i].set_xlabel(z)
            axs[1,i].set_ylabel('transformed')
        plt.savefig('/mp/nas2/ruihan/ExSeqProcessing2/output/step2_check_align/code{}/fov{}_large.jpg'.format(code,fov))
        plt.close()

        # ------------ Top left corner-------------------
        fig,axs = plt.subplots(2,5,figsize = (20,5))
        for i,z in enumerate(z_stacks):
            im = nd2ToSlice(args.nd2_path.format(args.ref_code, 4,'405'),fov, int(z), '405 SD')[:300,:300]
            axs[0,i].imshow(im,vmax = 600)
            axs[0,i].set_xlabel(z)
            axs[0,i].set_ylabel('fix')

        for i,z in enumerate(z_stacks):
            with h5py.File(args.h5_path_cropped.format(code,fov), "r") as f:
                im = f['405'][int(z),:300,:300]
                im = np.squeeze(im)
            axs[1,i].imshow(im,vmax = 600)
            axs[1,i].set_xlabel(z)
            axs[1,i].set_ylabel('transformed')
        plt.savefig('/mp/nas2/ruihan/ExSeqProcessing2/output/step2_check_align/code{}/fov{}_topleft.jpg'.format(code,fov))
        plt.close()

        # ------------ Bottom right corner----------
        fig,axs = plt.subplots(2,5,figsize = (20,5))
        for i,z in enumerate(z_stacks):
            im = nd2ToSlice(args.nd2_path.format(args.ref_code, 4,'405'),fov, int(z), '405 SD')[1700:,1700:]
            axs[0,i].imshow(im,vmax = 600)
            axs[0,i].set_xlabel(z)
            axs[0,i].set_ylabel('fix')

        for i,z in enumerate(z_stacks):
            with h5py.File(args.h5_path_cropped.format(code,fov), "r") as f:
                im = f['405'][int(z),1700:,1700:]
                im = np.squeeze(im)
            axs[1,i].imshow(im,vmax = 600)
            axs[1,i].set_xlabel(z)
            axs[1,i].set_ylabel('transformed')
        plt.savefig('/mp/nas2/ruihan/ExSeqProcessing2/output/step2_check_align/code{}/fov{}_bottomright.jpg'.format(code,fov))
        plt.close()


def transform_other_function(args,tasks_queue,q_lock,mode):

    import multiprocessing
    import queue
    import h5py
    import numpy as np
    import SimpleITK as sitk
    from exm.io.io import nd2ToVol

    while True: # Check for remaining task in the Queue

        try:
            with q_lock:
                fov,code = tasks_queue.get_nowait()
                print('Remaining tasks to process : {}'.format(tasks_queue.qsize()))
        except queue.Empty:
            print("No task left for "+ multiprocessing.current_process().name)
            break
        else:

            if tuple([code,fov]) not in args.starting:
                continue
            print(code,fov,'----------------------')
            
            # Load the start position
            fix_start,mov_start,last = args.starting[tuple([code,fov])]

            with h5py.File(args.h5_name.format(code,fov), 'a') as f:
                
                for channel_name_ind,channel_name in enumerate(args.channel_names):

                    if mode == '405':
                        if channel_name != '405': continue
                    elif mode == 'four':
                        if channel_name == '405': continue
                    if channel_name in f.keys():
                        continue

                    # Load the moving volume
                    mov_vol = nd2ToVol(args.nd2_path.format(code,channel_name,channel_name_ind), fov, channel_name)
                    mov_vol_sitk = sitk.GetImageFromArray(mov_vol)
                    mov_vol_sitk.SetSpacing([1.625,1.625,4.0])

                    # Read the transform map
                    transform_map = sitk.ReadParameterFile(args.tform_path.format(code,fov))
                    
                    # Change the size
                    transform_map["Size"] = tuple([str(x) for x in mov_vol.shape[::-1]])

                    # Shift the start
                    trans_um = np.array([float(x) for x in transform_map["TransformParameters"]])
                    trans_um[-1] -= (fix_start-mov_start)*4
                    transform_map["TransformParameters"] = tuple([str(x) for x in trans_um])     

                    # Center of rotation
                    cen_um = np.array([float(x) for x in transform_map['CenterOfRotationPoint']])   
                    cen_um[-1] += mov_start*4
                    transform_map['CenterOfRotationPoint'] = tuple([str(x) for x in cen_um])  

                    # Apply the transform
                    transformix = sitk.TransformixImageFilter()
                    transformix.SetTransformParameterMap(transform_map)
                    transformix.SetMovingImage(mov_vol_sitk)
                    transformix.Execute()
                    out = sitk.GetArrayFromImage(transformix.GetResultImage())

                    with h5py.File(args.h5_path.format(code,fov), 'a') as f:
                        f.create_dataset(channel_name, out.shape, dtype=out.dtype, data = out)                 


def transform_other_code(args,code_fov_pairs,num_cpu=8, mode='all'):
        
    import os
    import multiprocessing 
    import queue # imported for using queue.Empty exception

    os.environ["OMP_NUM_THREADS"] = "1"

    # Use a quarter of the available CPU resources to finish the tasks; you can increase this if the server is accessible for this task only.
    if num_cpu == None:
        cpu_execution_core = multiprocessing.cpu_count() / 4
    else:
        cpu_execution_core = num_cpu
    # List to hold the child processes.
    child_processes = [] 
    # Queue to hold all the puncta extraction tasks.
    tasks_queue = multiprocessing.Queue() 
    # Queue lock to avoid race condition.
    q_lock = multiprocessing.Lock()
    # Get the extraction tasks starting time. 
        
    # Clear the child processes list.
    child_processes = [] 

    # Add all the align405 to the queue.
    for code,fov in code_fov_pairs:
        tasks_queue.put((fov,code))

    for w in range(int(cpu_execution_core)):
        p = multiprocessing.Process(target=transform_other_function, args=(args,tasks_queue,q_lock,mode))
        child_processes.append(p)
        p.start()

    for p in child_processes:
        p.join()

    args.send_slack('transform_other_function finished!')

