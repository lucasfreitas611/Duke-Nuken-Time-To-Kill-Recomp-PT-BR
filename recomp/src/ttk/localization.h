#pragma once
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>

// Display-only localization. Never translate profile keys, input tokens or
// persisted game data. English remains available with DNTTK_LANGUAGE=en.
namespace ttk::ptbr {
inline bool enabled() {
    const char* lang=std::getenv("DNTTK_LANGUAGE");
    return !lang || !std::strcmp(lang,"pt-BR") || !std::strcmp(lang,"pt_BR");
}
inline const std::unordered_map<std::string,std::string>& catalog() {
    static const std::unordered_map<std::string,std::string> value={
#include "pt_br.inc"
    };
    return value;
}
inline std::string translate(const std::string& source) {
    if(!enabled() || source.empty())return source;
    const auto& map=catalog();
    if(auto it=map.find(source);it!=map.end())return it->second;
    // Labels acquire colons and padding at layout time.
    const auto start=source.find_first_not_of(' '),end=source.find_last_not_of(" :");
    if(start!=std::string::npos && end!=std::string::npos) {
        const auto core=source.substr(start,end-start+1);
        if(auto it=map.find(core);it!=map.end())return source.substr(0,start)+it->second+source.substr(end+1);
    }
    const std::string next=". NEXT LAUNCH";
    if(source.size()>next.size() && source.compare(source.size()-next.size(),next.size(),next)==0)
        return translate(source.substr(0,source.size()-next.size()))+". AO REABRIR O JOGO";
    const std::string binding=". CONFIRM, THEN PRESS THE NEW KEY";
    if(source.size()>binding.size() && source.compare(source.size()-binding.size(),binding.size(),binding)==0)
        return translate(source.substr(0,source.size()-binding.size()))+". CONFIRME E PRESSIONE A NOVA TECLA";
    // Dynamic labels are translated in segments, retaining numbers and keys.
    for(const char* prefix:{"DIFFICULTY: ","SLOT ","LEVEL ","PLAYER ","CHALLENGE STAGE "}) {
        const size_t n=std::strlen(prefix);
        if(source.compare(0,n,prefix)==0) {
            const std::string key(prefix,n-1);
            std::string tail=source.substr(n);
            const auto separator=tail.find(" - ");
            if(separator!=std::string::npos)tail=tail.substr(0,separator+3)+translate(tail.substr(separator+3));
            else tail=translate(tail);
            return translate(key)+" "+tail;
        }
    }
    const auto of=source.find(" OF ");
    if(of!=std::string::npos && !source.empty() && source[0]>='0' && source[0]<='9')
        return source.substr(0,of)+" DE "+source.substr(of+4);
    for(const char* tail:{" CONTINUE REMAINING"," CONTINUES REMAINING"}) {
        const size_t n=std::strlen(tail);
        if(source.size()>n && source.compare(source.size()-n,n,tail)==0)
            return source.substr(0,source.size()-n)+" VIDAS RESTANTES";
    }
    return source;
}

// One byte per glyph for both the guest font and host font layout. The pack
// stays unchanged: Portuguese diacritics are composed over its own letters.
inline std::string glyphs(const std::string& text) {
    std::string out;
    for(size_t i=0;i<text.size();++i) {
        unsigned c=(unsigned char)text[i];
        if(c==0xc3 && i+1<text.size() && ((unsigned char)text[i+1]&0xc0)==0x80) {
            c=0xc0+((unsigned char)text[++i]&0x3f);
        }
        // The game's typography is uppercase, including accented letters.
        if(c>=0xe0 && c<=0xfe && c!=0xf7)c-=0x20;
        out+=char(c);
    }
    return out;
}
inline unsigned base(unsigned c) {
    switch(c) {
    case 0xc0:case 0xc1:case 0xc2:case 0xc3:return 'A';
    case 0xc7:return 'C';case 0xc9:case 0xca:return 'E';
    case 0xcd:return 'I';case 0xd3:case 0xd4:case 0xd5:return 'O';
    case 0xda:case 0xdc:return 'U';default:return c;
    }
}
// Five-pixel-wide, three-row accents; cedilla is placed below the letter.
inline const char* accent(unsigned c) {
    switch(c) {
    case 0xc1:case 0xc9:case 0xcd:case 0xd3:case 0xda:return "001000100000000";
    case 0xc0:return "010000010000000";
    case 0xc2:case 0xca:case 0xd4:return "001000101000000";
    case 0xc3:case 0xd5:return "010101010000000";
    case 0xc7:return "001000001000100";
    case 0xdc:return "010100000000000";
    default:return nullptr;
    }
}
}
