#include "localization.h"
#include "ttk_font.h"
#include <cassert>
#include <cstdio>
#include <vector>
namespace ttk {bool input_modernized(){return true;}}
static void env(const char* key,const char* value) {
#ifdef _WIN32
    _putenv_s(key,value);
#else
    setenv(key,value,1);
#endif
}
int main(int argc,char** argv) {
    assert(argc==2);env("DNTTK_FONT_PACK",argv[1]);env("DNTTK_LANGUAGE","pt-BR");
    using namespace ttk::ptbr;
    assert(translate("OPTIONS")=="OPÇÕES");
    assert(translate("CONTROL SCHEME:")=="ESQUEMA DE CONTROLE:");
    assert(translate("DIFFICULTY: GET SOME")=="DIFICULDADE: MANDA VER");
    assert(translate("12 OF 20")=="12 DE 20");
    assert(translate("CAMERA. NEXT LAUNCH")=="CÂMERA. AO REABRIR O JOGO");
    assert(translate("DNTTK_CONTROL_SCHEME")=="DNTTK_CONTROL_SCHEME");
    assert(translate("Ctrl+W")=="Ctrl+W");
    const std::string letters=glyphs("ÀÁÂÃÇÉÊÍÓÔÕÚÜ");
    assert(letters.size()==13 && glyphs("opções").size()==6);
    std::vector<uint32_t> a(1024*256),b(a.size());
    for(unsigned char c:letters) {
        assert(accent(c));
        const char accented[2]={char(c),0},plain[2]={char(base(c)),0};
        for(int set:{0,1,2,3,6,8,9}) {
            std::fill(a.begin(),a.end(),0);std::fill(b.begin(),b.end(),0);
            assert(ttk_font_draw(set,accented,a.data(),1024,256,8,8)>0);
            assert(ttk_font_draw(set,plain,b.data(),1024,256,8,8)>0);
            assert(ttk_font_text_width(set,accented)==ttk_font_text_width(set,plain));
            assert(a!=b);
        }
    }
    for(int style:{0,1,2,3})for(int available:{304,624}) {
        int w=0,h=0;
        assert(ttk_font_rasterize("OPÇÕES: CÂMERA, RESOLUÇÃO, MISSÃO",style,a.data(),1024,256,available,&w,&h));
        assert(w<=available && h<=256);
    }
    env("DNTTK_LANGUAGE","en");assert(translate("OPTIONS")=="OPTIONS");
    std::puts("PT-BR: translation, fallback, glyph composition and wrapping passed");
}
