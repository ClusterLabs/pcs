require 'sinatra'

@nodes = (1..7)
  
get '/' do
  @nodes = (1..7)
  @cur_node = 1
  erb :index
end

get '/nodes/?' do
  @nodes = (1..7)
  @cur_node = 1
  erb :index
end

get '/nodes/:node' do
  @nodes = {} 
  (1..7).each do |i|
    @nodes[i] = [i, "Node #{i}", "node#{i}.lab.msp.redhat.com"]
  end
  @cur_node = params[:node].to_i
  if @cur_node == 0 then
    @cur_node = @nodes[1]
  else
    @cur_node = @nodes[@cur_node]
  end
  print "TEST"
  print @nodes
  erb :index
end

get '*' do
  @cur_node = 1
  @nodes = [1,2]
  erb :index
end
