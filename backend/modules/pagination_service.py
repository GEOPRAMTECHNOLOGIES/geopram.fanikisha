def page_limit(value,default=50):
    try:return max(1,min(int(value),500))
    except:return default
