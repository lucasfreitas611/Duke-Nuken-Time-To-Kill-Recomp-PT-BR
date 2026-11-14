#pragma once
#include <cstdlib>
#ifdef _WIN32
static int setenv(const char* name,const char* value,int overwrite) {
    if(!overwrite && std::getenv(name))return 0;
    return _putenv_s(name,value);
}
static int unsetenv(const char* name) {return _putenv_s(name,"");}
#endif
