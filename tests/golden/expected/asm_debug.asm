section .text

extern print_int
extern print_string
extern read_int
extern printf
extern scanf
extern malloc
extern free
extern strlen
extern pow

global main
main:
    push rbp
    mov rbp, rsp
    sub rsp, 16
.main_entry:
%line 2 input.src
    ; x = ALLOCA 4    # allocate x
    mov dword [rbp-4], 5
    mov eax, dword [rbp-4]
    mov dword [rbp-8], eax
%line 3 input.src
    mov eax, dword [rbp-8]
    mov rsp, rbp
    pop rbp
    ret

section .note.GNU-stack noalloc noexec nowrite progbits