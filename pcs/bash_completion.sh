# bash completion for pcs
_pcs_completion(){
  
  LENGTHS=()
  for WORD in "${COMP_WORDS[@]}"; do
    LENGTHS+=(${#WORD})
  done


  COMPREPLY=( $( \
    env COMP_WORDS="${COMP_WORDS[*]}" \
    COMP_LENGTHS="${LENGTHS[*]}" \
    COMP_CWORD=$COMP_CWORD \
    PCS_AUTO_COMPLETE=1 pcs \
  ) )

  #examples what we get:
  #pcs
  #COMP_WORDS: pcs COMP_LENGTHS: 3
  #pcs co
  #COMP_WORDS: pcs co COMP_LENGTHS: 3 2
  #      pcs          config        
  #COMP_WORDS: pcs config COMP_LENGTHS: 3 6
  #      pcs          config       "  
  #COMP_WORDS: pcs config "    COMP_LENGTHS: 3 6 4
  #      pcs          config       "'\\n
  #COMP_WORDS: pcs config "'\\n COMP_LENGTHS: 3 6 5'"
}

# -o default
#   Use readline's default filename completion if the compspec generates no
#   matches.
# -F function
#   The shell function function is executed in the current shell environment. 
#   When it finishes, the possible completions are retrieved from the value of
#   the COMPREPLY array variable.

complete -o default -F _pcs_completion pcs
