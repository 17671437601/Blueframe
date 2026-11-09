import multiprocessing

from blueframe_desktop.launcher import main

multiprocessing.freeze_support()
raise SystemExit(main())
