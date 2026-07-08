import sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    content = f.read()

old = '''.method public final isVip()Z
    .registers 3
    .line 1
    new-instance v0, Lcom/dugu/user/ui/login/BuyManagerImpl$isVip$1;
    .line 3
    const/4 v1, 0x0
    .line 4
    invoke-direct {v0, p0, v1}, Lcom/dugu/user/ui/login/BuyManagerImpl$isVip$1;-><init>(Lcom/dugu/user/ui/login/BuyManagerImpl;Lkotlin/coroutines/Continuation;)V
    .line 7
    invoke-static {v0}, Lx50;->b(Lkotlin/jvm/functions/Function2;)Ljava/lang/Object;
    .line 10
    move-result-object p0
    .line 11
    check-cast p0, Ljava/lang/Boolean;
    .line 13
    invoke-virtual {p0}, Ljava/lang/Boolean;->booleanValue()Z
    .line 16
    move-result p0
    .line 17
    return p0
.end method'''

new = '''.method public final isVip()Z
    .registers 2
    const/4 v0, 0x1
    return v0
.end method'''

content = content.replace(old, new)
with open(sys.argv[2], 'w', encoding='utf-8') as f:
    f.write(content)
print("Done! Replaced isVip() successfully.")
