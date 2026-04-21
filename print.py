for i, l in enumerate(open('src/aiplatform/worker.py')):
    if 'subject=f"Your Free' in l:
        for idx in range(i-5, i+15):
             print(f"{idx}: {repr(open('src/aiplatform/worker.py').readlines()[idx])}")